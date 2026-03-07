"""開示文書変更スコアリングサービス (T012)

スコア計算ロジック:
  - checklist_coverage_score: チェックリスト一致率 (0-100)
      = evaluate_and_save の coverage_rate × 100
  - change_intensity_score: 変更語彙の濃度 (0-100)
      = min(変更語彙マッチ数 / len(変更語彙リスト) × 200, 100.0)
      理由: 半分の変更語彙が登場すれば充分高い変化強度とみなす
  - overall_risk_score: 総合リスクスコア (0-100)
      = round(0.6 × checklist_coverage_score + 0.4 × change_intensity_score, 1)
      理由: チェックリスト一致率をより重視（開示義務の充足が主目的）
  - risk_level: "low" (<40) / "medium" (40-69) / "high" (>=70)

設計方針:
  - compute_scores は純粋関数（DB非依存・テスト容易）
  - _get_connection は checklist_eval_service から再利用
  - score_document / get_score_history が公開 API
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from api.services.checklist_eval_service import _get_connection, evaluate_and_save

# ─── 変更語彙リスト ──────────────────────────────────────────────────────────

CHANGE_VOCABULARY: list[str] = [
    "変更", "改正", "廃止", "新設", "追加", "削除", "修正", "見直し",
]

# ─── DB スキーマ ──────────────────────────────────────────────────────────────

_CREATE_SCORE_HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS score_history (
    score_id                 TEXT PRIMARY KEY,
    scored_at                TEXT NOT NULL,
    text_snippet             TEXT NOT NULL,
    checklist_coverage_score REAL NOT NULL,
    change_intensity_score   REAL NOT NULL,
    overall_risk_score       REAL NOT NULL,
    risk_level               TEXT NOT NULL,
    top_matched_items        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_score_history_at ON score_history(scored_at DESC);
"""


def _get_score_connection() -> sqlite3.Connection:
    """スコア履歴 DB 接続を返す（eval_history と同一 DB ファイルを使用）。"""
    conn = _get_connection()
    conn.executescript(_CREATE_SCORE_HISTORY_SQL)
    return conn


# ─── 純粋関数（ユニットテスト可能） ───────────────────────────────────────────

def compute_change_intensity(text: str, vocab: list[str] = CHANGE_VOCABULARY) -> float:
    """変更語彙の濃度スコア (0.0〜100.0) を計算する。

    score = min(マッチした変更語彙の種類数 / len(vocab) × 200, 100.0)

    Args:
        text: 開示文書テキスト。
        vocab: 変更語彙リスト（デフォルト: CHANGE_VOCABULARY）。

    Returns:
        0.0〜100.0 の float（小数点1桁）。
    """
    if not text.strip() or not vocab:
        return 0.0
    matched = sum(1 for kw in vocab if kw in text)
    score = min(matched / len(vocab) * 200.0, 100.0)
    return round(score, 1)


def compute_risk_level(overall_risk_score: float) -> str:
    """総合リスクスコアからリスクレベルを返す。

    Args:
        overall_risk_score: 0.0〜100.0。

    Returns:
        "low" (< 40) / "medium" (40〜69) / "high" (>= 70)。
    """
    if overall_risk_score >= 70.0:
        return "high"
    if overall_risk_score >= 40.0:
        return "medium"
    return "low"


def compute_scores(
    coverage_rate: float,
    change_intensity_score: float,
) -> dict:
    """個別スコアから総合スコアとリスクレベルを計算する。

    Args:
        coverage_rate: チェックリスト一致率 (0.0〜1.0)。
        change_intensity_score: 変更語彙スコア (0.0〜100.0)。

    Returns:
        {
            "checklist_coverage_score": float,  # 0-100
            "change_intensity_score": float,    # 0-100
            "overall_risk_score": float,        # 0-100
            "risk_level": str,                  # low/medium/high
        }
    """
    checklist_coverage_score = round(coverage_rate * 100.0, 1)
    overall_risk_score = round(
        0.6 * checklist_coverage_score + 0.4 * change_intensity_score, 1
    )
    return {
        "checklist_coverage_score": checklist_coverage_score,
        "change_intensity_score": change_intensity_score,
        "overall_risk_score": overall_risk_score,
        "risk_level": compute_risk_level(overall_risk_score),
    }


# ─── 公開 API ──────────────────────────────────────────────────────────────────

def score_document(disclosure_text: str) -> dict:
    """開示文書を解析してスコアリング結果を返し、score_history に保存する。

    Args:
        disclosure_text: 開示文書テキスト。

    Returns:
        {
            "score_id": str (UUID4),
            "scored_at": str (ISO 8601),
            "overall_risk_score": float,
            "checklist_coverage_score": float,
            "change_intensity_score": float,
            "risk_level": str,
            "top_matched_items": list[dict],
        }

    Raises:
        ValueError: disclosure_text が空の場合。
    """
    if not disclosure_text.strip():
        raise ValueError("disclosure_text が空です")

    # チェックリスト評価（coverage_rate 取得）
    eval_result = evaluate_and_save(disclosure_text)
    coverage_rate = eval_result["coverage_rate"]

    # 変更語彙スコア
    change_intensity = compute_change_intensity(disclosure_text)

    # スコア計算
    scores = compute_scores(coverage_rate, change_intensity)

    # top_matched_items: evaluate_and_save は matched_count しか返さないので
    # get_evaluation_detail で detail を取得
    from api.services.checklist_eval_service import get_evaluation_detail
    detail = get_evaluation_detail(eval_result["eval_id"])
    results = detail["results"] if detail else []
    top_matched = [
        {"item_id": r["id"], "item_name": r["item"]}
        for r in results
        if r.get("matched", False)
    ][:5]  # 上位5件

    score_id = str(uuid.uuid4())
    scored_at = datetime.now().isoformat(timespec="seconds")
    text_snippet = disclosure_text[:200]

    conn = _get_score_connection()
    try:
        conn.execute(
            """INSERT INTO score_history
               (score_id, scored_at, text_snippet,
                checklist_coverage_score, change_intensity_score,
                overall_risk_score, risk_level, top_matched_items)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                score_id,
                scored_at,
                text_snippet,
                scores["checklist_coverage_score"],
                scores["change_intensity_score"],
                scores["overall_risk_score"],
                scores["risk_level"],
                json.dumps(top_matched, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "score_id": score_id,
        "scored_at": scored_at,
        "overall_risk_score": scores["overall_risk_score"],
        "checklist_coverage_score": scores["checklist_coverage_score"],
        "change_intensity_score": scores["change_intensity_score"],
        "risk_level": scores["risk_level"],
        "top_matched_items": top_matched,
    }


def get_score_history(limit: int = 10) -> list[dict]:
    """スコアリング履歴の最新 limit 件を返す。"""
    conn = _get_score_connection()
    try:
        rows = conn.execute(
            """SELECT score_id, scored_at, text_snippet,
                      checklist_coverage_score, change_intensity_score,
                      overall_risk_score, risk_level, top_matched_items
               FROM score_history
               ORDER BY scored_at DESC, rowid DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["top_matched_items"] = json.loads(d["top_matched_items"])
            result.append(d)
        return result
    finally:
        conn.close()
