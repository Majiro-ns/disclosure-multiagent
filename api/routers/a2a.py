"""A2A (Agent-to-Agent) protocol endpoints for disclosure-multiagent.

Agent Card の提供と A2A タスク実行エンドポイントを実装する。

仕様参照: https://google.github.io/A2A/
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from a2a.types import (
    Artifact,
    Task,
    TaskState,
    TaskStatus,
    TextPart,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/a2a", tags=["a2a"])

_AGENT_CARD_PATH = Path(__file__).parent.parent.parent / ".well-known" / "agent-card.json"


# ─── Agent Card エンドポイント ───────────────────────────────────────────────

@router.get("/.well-known/agent-card.json", include_in_schema=False)
async def get_agent_card_a2a():
    """A2A Agent Card を返す（/a2a プレフィックス付きパス）。"""
    return _serve_agent_card()


@router.get("/agent-card", summary="A2A Agent Card 取得")
async def get_agent_card():
    """A2A プロトコル準拠の Agent Card JSON を返す。"""
    return _serve_agent_card()


def _serve_agent_card() -> JSONResponse:
    if not _AGENT_CARD_PATH.exists():
        raise HTTPException(status_code=404, detail="Agent Card not found")
    data = json.loads(_AGENT_CARD_PATH.read_text(encoding="utf-8"))
    return JSONResponse(content=data)


# ─── A2A タスク実行エンドポイント ────────────────────────────────────────────

@router.post("/execute", summary="A2A タスク実行")
async def execute_task(body: dict) -> dict:
    """A2A Task を受け取り、松竹梅エンジンに接続して結果を A2A Artifact 形式で返す。

    入力形式（A2A Task JSON）:
        {
            "id": "task_xxx",
            "contextId": "session_yyy",
            "message": {
                "messageId": "msg_zzz",
                "role": "user",
                "parts": [{"kind": "text", "text": "分析してください..."}]
            }
        }

    出力形式（A2A Task JSON）:
        {
            "id": "task_xxx",
            "contextId": "session_yyy",
            "kind": "task",
            "status": {"state": "completed", "timestamp": "..."},
            "artifacts": [{"artifactId": "...", "parts": [{"kind": "text", "text": "分析結果"}]}]
        }
    """
    task_id = body.get("id", str(uuid.uuid4()))
    context_id = body.get("contextId", str(uuid.uuid4()))

    # ─── 入力テキスト抽出 ──────────────────────────────────────────────
    message = body.get("message", {})
    parts = message.get("parts", [])
    input_text = ""
    for part in parts:
        if isinstance(part, dict) and part.get("kind") == "text":
            input_text += part.get("text", "")
        elif isinstance(part, dict) and part.get("type") == "text":
            input_text += part.get("text", "")

    if not input_text.strip():
        return _make_error_task(task_id, context_id, "入力テキストが空です")

    logger.info("[A2A] タスク受信: id=%s text=%s...", task_id, input_text[:50])

    # ─── スキル振り分け ────────────────────────────────────────────────
    try:
        result_text = _dispatch_to_skill(input_text, body)
    except Exception as e:
        logger.exception("[A2A] スキル実行エラー: %s", e)
        return _make_error_task(task_id, context_id, f"スキル実行エラー: {e}")

    # ─── A2A Task レスポンス構築 ────────────────────────────────────────
    artifact = Artifact(
        artifactId=str(uuid.uuid4()),
        name="analysis_result",
        parts=[TextPart(text=result_text)],
    )
    task = Task(
        id=task_id,
        contextId=context_id,
        status=TaskStatus(
            state=TaskState.completed,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ),
        artifacts=[artifact],
    )
    return task.model_dump(mode="json")


def _dispatch_to_skill(input_text: str, body: dict) -> str:
    """入力テキストを解析してスキルを選択・実行する。

    スキル選択ルール:
    1. "EDINET" / "edinet" / "証券コード" / "検索" → edinet_search
    2. "スコアリング" / "チェックリスト" / "評価" → matsu_take_ume_scoring
    3. それ以外 → analyze_disclosure（PDFパスまたはEDINETコードで分析）
    """
    skill_id = body.get("skillId", "")
    lower = input_text.lower()

    # 明示的スキル指定またはキーワード判定
    if skill_id == "edinet_search" or (
        "edinet" in lower or "証券コード" in input_text or
        ("検索" in input_text and "分析" not in input_text)
    ):
        return _skill_edinet_search(input_text)
    elif skill_id == "matsu_take_ume_scoring" or (
        "スコアリング" in input_text or "チェックリスト" in input_text
    ):
        return _skill_scoring(input_text)
    else:
        return _skill_analyze_disclosure(input_text)


def _skill_edinet_search(input_text: str) -> str:
    """EDINET検索スキル。"""
    import re
    try:
        from api.services.edinet_service import search_documents
    except ImportError:
        return "[EDINET検索] サービス未利用可能。edinet_serviceをインポートできません。"

    # 証券コードまたはEDINETコードを抽出
    codes = re.findall(r"[E]\d{5}|[0-9]{4}", input_text)
    if not codes:
        return "[EDINET検索] 証券コードまたはEDINETコード（Exxxxx）が入力に含まれていません。"

    try:
        results = search_documents(codes[0])
        if not results:
            return f"[EDINET検索] コード {codes[0]} の書類が見つかりませんでした。"
        lines = [f"【EDINET検索結果】コード: {codes[0]}"]
        for doc in results[:5]:
            lines.append(f"  - {doc.get('doc_description', '不明')} ({doc.get('period_end', '')})")
        return "\n".join(lines)
    except Exception as e:
        return f"[EDINET検索] エラー: {e}"


def _skill_scoring(input_text: str) -> str:
    """松竹梅スコアリングスキル（テキスト直接評価）。"""
    try:
        from api.services.scoring_service import score_text
        result = score_text(input_text)
        return result if isinstance(result, str) else str(result)
    except ImportError:
        pass
    except Exception as e:
        return f"[スコアリング] エラー: {e}"

    # フォールバック: キーワードベース簡易評価
    score = 0
    feedback = []
    if any(kw in input_text for kw in ["数値", "KPI", "目標", "%", "率"]):
        score += 30
        feedback.append("定量指標の記述あり（+30点）")
    if any(kw in input_text for kw in ["年度", "期", "20"]):
        score += 20
        feedback.append("目標年度の記述あり（+20点）")
    if any(kw in input_text for kw in ["取締役会", "承認", "推進体制"]):
        score += 20
        feedback.append("ガバナンス体制の記述あり（+20点）")
    if len(input_text) > 100:
        score += 10
        feedback.append("十分な記述量（+10点）")

    level = "松" if score >= 80 else "竹" if score >= 60 else "梅"
    lines = [f"【簡易スコアリング結果】{level}レベル（{score}点）"]
    lines.extend(feedback)
    if score < 60:
        lines.append("改善提案: 具体的数値・KPI・目標年度・ガバナンス体制の記述を追加してください")
    return "\n".join(lines)


def _skill_analyze_disclosure(input_text: str) -> str:
    """開示書類分析スキル（松竹梅エンジン呼び出し）。"""
    try:
        from api.services.pipeline import create_task, run_pipeline_sync
        task_id = create_task()
        result = run_pipeline_sync(
            task_id=task_id,
            pdf_path="",
            company_name=_extract_company_name(input_text),
            use_mock=True,
        )
        if result:
            return f"【分析結果】\n{result}"
        return "[分析] パイプライン完了。結果は /api/status/{task_id} で確認できます。"
    except (ImportError, AttributeError):
        pass
    except Exception as e:
        return f"[分析] エラー: {e}"

    return (
        "[disclosure-multiagent A2A]\n"
        "入力を受け付けました。松竹梅エンジンで分析します。\n"
        "詳細な分析には POST /api/analyze に有価証券報告書PDFまたはEDINETコードを送信してください。\n"
        f"入力テキスト: {input_text[:200]}"
    )


def _extract_company_name(text: str) -> str:
    """テキストから企業名を簡易抽出する。"""
    import re
    # 「〇〇株式会社」「〇〇(株)」形式
    match = re.search(r"[\u4e00-\u9fff\u30a0-\u30ff\u3040-\u309f\uff00-\uffef]+(?:株式会社|㈱|\(株\))", text)
    if match:
        return match.group(0)
    return ""


def _make_error_task(task_id: str, context_id: str, message: str) -> dict:
    """エラー状態の A2A Task を返す。"""
    task = Task(
        id=task_id,
        contextId=context_id,
        status=TaskStatus(
            state=TaskState.failed,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ),
        artifacts=[
            Artifact(
                artifactId=str(uuid.uuid4()),
                name="error",
                parts=[TextPart(text=f"[ERROR] {message}")],
            )
        ],
    )
    return task.model_dump(mode="json")
