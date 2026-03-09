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

松竹梅ティアスコア (C06: cmd_374k_a7, C06差替: cmd_375k_a7):
  - tier_score: 0〜100 の整数
      = カバー済み必須項目数 / 全必須項目数 × 100
  - tier_label: "未達" (<60) / "梅" (60-79) / "竹" (80-94) / "松" (>=95)
  - upgrade_items: 次ティアに必要な開示項目リスト

  差替後（cmd_375k_a7）:
  - load_law_entries(): laws/*.yaml から tier_requirement 付き全68エントリを読み込む
  - _derive_gap_results(): キーワードマッチングで gap_results を生成（M3代替）
  - compute_tier_score(gap_results, law_entries, tier_level="ume"):
      tier_level = "ume"|"take"|"matsu" で評価対象ティアを指定
      後方互換: tier_requirement が文字列の場合もそのまま動作
  - _get_upgrade_items_from_laws(): 実データからアップグレード項目を抽出

設計方針:
  - compute_scores は純粋関数（DB非依存・テスト容易）
  - _get_connection は checklist_eval_service から再利用
  - score_document / get_score_history が公開 API
  - compute_tier_score / get_tier_label / get_upgrade_items は純粋関数（後方互換）
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from api.services.checklist_eval_service import _get_connection, evaluate_and_save

# ─── 変更語彙リスト ──────────────────────────────────────────────────────────

CHANGE_VOCABULARY: list[str] = [
    "変更", "改正", "廃止", "新設", "追加", "削除", "修正", "見直し",
]

# ─── 松竹梅ティアスコア定数（C06: cmd_374k_a7）─────────────────────────────────

TIER_UME_MIN: int = 60   # 梅ライン（法令必須をすべてカバー）
TIER_TAKE_MIN: int = 80  # 竹ライン（推奨項目もカバー）
TIER_MATSU_MIN: int = 95 # 松ライン（任意項目もほぼ全カバー）

# A6のC07（tier_requirement追加）完了前のモックデータ
# 必須 10件 + 推奨 5件
MOCK_LAW_ENTRIES: list[dict] = [
    {"id": "LAW-001", "title": "人的資本KPI開示（従業員エンゲージメント）", "tier_requirement": "必須"},
    {"id": "LAW-002", "title": "人的資本KPI開示（女性管理職比率）", "tier_requirement": "必須"},
    {"id": "LAW-003", "title": "人的資本KPI開示（男性育休取得率）", "tier_requirement": "必須"},
    {"id": "LAW-004", "title": "人的資本KPI開示（研修時間・研修費用）", "tier_requirement": "必須"},
    {"id": "LAW-005", "title": "人的資本KPI開示（離職率）", "tier_requirement": "必須"},
    {"id": "LAW-006", "title": "有価証券報告書・サステナビリティ情報の記載", "tier_requirement": "必須"},
    {"id": "LAW-007", "title": "コーポレートガバナンス報告書との整合性", "tier_requirement": "必須"},
    {"id": "LAW-008", "title": "SSBJ基準に基づく気候変動リスク開示", "tier_requirement": "必須"},
    {"id": "LAW-009", "title": "GHG排出量（Scope1・Scope2）の開示", "tier_requirement": "必須"},
    {"id": "LAW-010", "title": "サプライチェーン人権リスク対応の開示", "tier_requirement": "必須"},
    {"id": "LAW-011", "title": "SSBJ早期適用宣言", "tier_requirement": "推奨"},
    {"id": "LAW-012", "title": "Scope3排出量の開示", "tier_requirement": "推奨"},
    {"id": "LAW-013", "title": "人的資本投資ROIの定量開示", "tier_requirement": "推奨"},
    {"id": "LAW-014", "title": "気候変動シナリオ分析（1.5℃/4℃）の詳細開示", "tier_requirement": "推奨"},
    {"id": "LAW-015", "title": "TNFD（自然関連財務情報）への対応状況", "tier_requirement": "推奨"},
]

# 各ティア到達に必要な代表的開示項目
_UPGRADE_ITEMS: dict[str, list[str]] = {
    "梅": [
        "有価証券報告書への人的資本KPI追記（エンゲージメント・離職率）",
        "GHG排出量（Scope1・Scope2）の開示",
        "サステナビリティ情報のサステナビリティ方針記載",
    ],
    "竹": [
        "有価証券報告書への人的資本KPI追記",
        "SSBJ早期適用宣言",
        "Scope3排出量の開示（サプライチェーン全体）",
    ],
    "松": [
        "TNFD（自然関連財務情報）への対応状況の開示",
        "気候変動シナリオ分析（1.5℃・4℃）の詳細開示",
        "人的資本投資ROIの定量開示（人材育成費用対効果）",
    ],
}

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


# ─── 松竹梅ティアスコア 純粋関数（C06: cmd_374k_a7）────────────────────────────


def compute_tier_score(
    gap_results: list[dict],
    law_entries: list[dict],
    tier_level: str = "ume",
) -> int:
    """法令エントリとギャップ分析結果から松竹梅ティアスコア (0〜100) を計算する。

    計算式: カバー済み必須項目数 / 全必須項目数 × 100
    「カバー済み」= has_gap が True でない項目（False または None）。
    law_entries に "必須" 項目がない場合は 0 を返す。

    Args:
        gap_results: M3ギャップ分析結果のリスト。各要素に "has_gap": bool|None を含む。
        law_entries: 法令エントリのリスト。各要素に "tier_requirement" を含む。
            tier_requirement は dict {"ume": ..., "take": ..., "matsu": ...} または
            後方互換のため文字列 "必須"/"推奨" 等もサポート。
        tier_level: 評価対象ティア。"ume" | "take" | "matsu"（デフォルト: "ume"）。

    Returns:
        0〜100 の整数。
    """
    def _is_required(entry: dict) -> bool:
        tier_req = entry.get("tier_requirement")
        if isinstance(tier_req, dict):
            # 実データ形式: {"ume": "必須", "take": "推奨", ...}
            return tier_req.get(tier_level, "対象外") == "必須"
        # 後方互換: 文字列形式（テスト用モックデータ）
        return tier_req == "必須"

    required_entries = [e for e in law_entries if _is_required(e)]
    required_count = len(required_entries)
    if required_count == 0:
        return 0

    # ID ベースマッチング（実データ）/ なければ全体集計（後方互換・テスト用モックデータ）
    gap_map: dict[str, bool] = {
        r.get("id"): bool(r.get("has_gap", True))
        for r in gap_results if r.get("id")
    }
    if gap_map:
        # 実データ: 必須エントリのギャップのみカウント
        required_gaps = sum(
            1 for e in required_entries
            if gap_map.get(e.get("id", ""), True) is True
        )
    else:
        # 後方互換: ID なしのモックデータ（既存テスト用）
        required_gaps = sum(1 for r in gap_results if r.get("has_gap") is True)

    covered = max(0, required_count - required_gaps)
    return min(100, round(covered / required_count * 100))


def load_law_entries() -> list[dict]:
    """laws/ 配下の全 YAML ファイルから tier_requirement 付きエントリを読み込む。

    tier_requirement フィールドを持つエントリのみ対象（A6 C07 完了分、現在 68 件）。

    Returns:
        各エントリの dict リスト。id / title / tier_requirement 等を含む。
    """
    laws_dir = Path(__file__).parent.parent.parent / "laws"
    entries: list[dict] = []
    for yaml_path in sorted(laws_dir.glob("*.yaml")):
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for amendment in data.get("amendments", []):
            if "tier_requirement" in amendment:
                entries.append(amendment)
    return entries


def _derive_gap_results(disclosure_text: str, law_entries: list[dict]) -> list[dict]:
    """開示テキストのキーワードマッチングから gap_results を生成する（M3 LLM 代替）。

    各法令エントリの required_items / title から抽出したキーワードが
    disclosure_text に含まれていれば has_gap=False（カバー済み）、
    含まれなければ has_gap=True（ギャップあり）とする。

    Args:
        disclosure_text: 開示文書テキスト。
        law_entries: load_law_entries() で取得した法令エントリリスト。

    Returns:
        [{"id": str, "has_gap": bool}, ...] のリスト（law_entries と同順）。
    """
    results: list[dict] = []
    for entry in law_entries:
        keywords: list[str] = []
        # required_items（最も具体的なキーワード群）
        keywords.extend(entry.get("required_items", []))
        # title から「—」「：」以降のキーフレーズを抽出
        title: str = entry.get("title", "")
        if "—" in title:
            keywords.append(title.split("—", 1)[1].strip())
        elif "：" in title:
            keywords.append(title.split("：", 1)[1].strip())
        else:
            keywords.append(title)
        # 3文字以上のキーワードがテキストに含まれればカバー済み
        covered = any(kw in disclosure_text for kw in keywords if len(kw) >= 3)
        results.append({"id": entry.get("id", ""), "has_gap": not covered})
    return results


def _get_upgrade_items_from_laws(
    gap_results: list[dict],
    law_entries: list[dict],
    tier_level: str,
) -> list[str]:
    """gap_results + 実 law_entries からアップグレードに必要な開示項目タイトルを返す。

    指定ティアで tier_requirement == "必須" かつ has_gap=True の項目を最大5件返す。

    Args:
        gap_results: _derive_gap_results() の出力。{"id": str, "has_gap": bool} のリスト。
        law_entries: load_law_entries() で取得した法令エントリリスト。
        tier_level: "ume" | "take" | "matsu"

    Returns:
        開示項目タイトルのリスト（最大5件）。
    """
    gap_map: dict[str, bool] = {r.get("id", ""): bool(r.get("has_gap", True)) for r in gap_results}
    items: list[str] = []
    for entry in law_entries:
        tier_req = entry.get("tier_requirement")
        if not isinstance(tier_req, dict):
            continue
        if tier_req.get(tier_level) != "必須":
            continue
        entry_id = entry.get("id", "")
        if gap_map.get(entry_id, True):  # has_gap=True → 未カバー → アップグレード対象
            items.append(entry.get("title", ""))
    return items[:5]


def get_tier_label(score: int) -> str:
    """ティアスコアから松竹梅ラベルを返す。

    - 95点以上: "松"
    - 80〜94点: "竹"
    - 60〜79点: "梅"
    - 59点以下: "未達"

    Args:
        score: 0〜100 の整数。

    Returns:
        "松" / "竹" / "梅" / "未達"
    """
    if score >= TIER_MATSU_MIN:
        return "松"
    if score >= TIER_TAKE_MIN:
        return "竹"
    if score >= TIER_UME_MIN:
        return "梅"
    return "未達"


def get_upgrade_items(score: int, target_tier: str) -> list[str]:
    """現在スコアから目標ティアに達するために必要な開示項目を返す。

    Args:
        score: 現在の tier_score (0〜100)。
        target_tier: "梅" | "竹" | "松"。

    Returns:
        推奨開示項目のリスト。既に目標ティア以上の場合は空リスト。

    Raises:
        ValueError: target_tier が "梅"/"竹"/"松" 以外の場合。
    """
    if target_tier not in ("梅", "竹", "松"):
        raise ValueError(
            f"target_tier は '梅'/'竹'/'松' のいずれかを指定してください: {target_tier!r}"
        )
    _tier_order = {"未達": 0, "梅": 1, "竹": 2, "松": 3}
    _target_order = {"梅": 1, "竹": 2, "松": 3}
    current_label = get_tier_label(score)
    if _tier_order.get(current_label, 0) >= _target_order[target_tier]:
        return []
    return list(_UPGRADE_ITEMS[target_tier])


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
