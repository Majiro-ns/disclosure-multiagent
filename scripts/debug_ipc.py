"""debug_ipc.py
==============
disclosure-multiagent デバッグモード用 ファイルベースIPC ユーティリティ。

【概要】
  M3/M4 の LLM 呼び出しを、API キーなしで Claude Code（足軽）が代替できるようにする。
  パイプラインが request_{uuid}.json を書き出し、足軽が読んで
  response_{uuid}.json を書くことでIPC通信を行う。

【ディレクトリ構成】
  /tmp/disclosure_debug/
    request_{uuid}.json  ← パイプラインが書く（単件 or バッチ）
    response_{uuid}.json ← 足軽（Claude Code）が書く（単件 or バッチ）

【単件 request JSON スキーマ】
  {
    "id": "uuid",
    "stage": "m3" | "m4",
    "system_prompt": "...",
    "user_prompt": "...",
    "batch": false,
    "created_at": "ISO8601"
  }

【単件 response JSON スキーマ】
  {
    "id": "uuid（request と同じ）",
    "content": "LLM応答テキスト",
    "created_at": "ISO8601"
  }

【バッチ request JSON スキーマ】
  {
    "id": "uuid",
    "stage": "m3" | "m4",
    "system_prompt": "...",
    "items": [{"index": 0, "user_prompt": "..."}, ...],
    "batch": true,
    "created_at": "ISO8601"
  }

【バッチ response JSON スキーマ】
  {
    "id": "uuid（request と同じ）",
    "results": [{"index": 0, "content": "..."}, ...],
    "created_at": "ISO8601"
  }

cmd_360k_a7d: 単件IPC実装 (2026-03-14)
cmd_360k_a7e: バッチIPC追加 (2026-03-14)
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# 定数
# ─────────────────────────────────────────────────────────
DEBUG_DIR = Path("/tmp/disclosure_debug")
POLL_INTERVAL = 1.0    # 秒
DEFAULT_TIMEOUT = 300  # 秒（5分、単件用）
BATCH_TIMEOUT = 600    # 秒（10分、バッチ用 — 量が多いため）


# ─────────────────────────────────────────────────────────
# IPC ユーティリティ関数
# ─────────────────────────────────────────────────────────

def ensure_debug_dir() -> None:
    """デバッグ用ディレクトリを作成する（冪等）。"""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────
# ステータス管理関数（cmd_360k_a6d）
# ─────────────────────────────────────────────────────────

def write_status(request_id: str, status: str) -> Path:
    """
    /tmp/disclosure_debug/status_{id}.json にステータスを書き出す。

    Args:
        request_id: UUID 文字列
        status: "pending" | "processing" | "done"

    Returns:
        書き込んだファイルのパス
    """
    ensure_debug_dir()
    status_path = DEBUG_DIR / f"status_{request_id}.json"
    payload = {
        "id": request_id,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.debug("[debug_ipc] ステータス更新: %s → %s", request_id, status)
    return status_path


def read_status(request_id: str) -> str | None:
    """
    status_{id}.json を読んでステータス文字列を返す。ファイル不在の場合は None。
    """
    status_path = DEBUG_DIR / f"status_{request_id}.json"
    if not status_path.exists():
        return None
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
        return data.get("status")
    except Exception:
        return None


def write_request(
    stage: str,
    system_prompt: str,
    user_prompt: str,
    request_id: str | None = None,
) -> str:
    """
    リクエスト JSON を /tmp/disclosure_debug/request_{id}.json に書き出す。

    Args:
        stage: "m3" または "m4"
        system_prompt: LLMに渡すシステムプロンプト
        user_prompt: LLMに渡すユーザープロンプト
        request_id: UUID 文字列（None の場合は自動生成）

    Returns:
        request_id（UUID 文字列）
    """
    ensure_debug_dir()
    request_id = request_id or str(uuid4())
    payload = {
        "id": request_id,
        "stage": stage,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    request_path = DEBUG_DIR / f"request_{request_id}.json"
    request_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_status(request_id, "pending")
    logger.info("[debug_ipc] リクエスト書き出し: %s (stage=%s)", request_path.name, stage)
    return request_id


def wait_for_response(request_id: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """
    response_{id}.json が出現するまでポーリングし、content を返す。

    Args:
        request_id: write_request() が返した UUID
        timeout: タイムアウト秒数（デフォルト 300 秒）

    Returns:
        response の content 文字列

    Raises:
        TimeoutError: timeout 秒以内に応答がない場合
        ValueError: response JSON のパースに失敗した場合
    """
    response_path = DEBUG_DIR / f"response_{request_id}.json"
    deadline = time.monotonic() + timeout
    logger.info(
        "[debug_ipc] 応答待機中: %s (タイムアウト=%ds)",
        response_path.name, int(timeout),
    )

    while time.monotonic() < deadline:
        if response_path.exists():
            try:
                data = json.loads(response_path.read_text(encoding="utf-8"))
                content = data.get("content", "")
                if not content:
                    raise ValueError(
                        f"response_{request_id}.json に 'content' キーがありません: {data}"
                    )
                write_status(request_id, "done")
                logger.info("[debug_ipc] 応答受信: %s (%d文字)", response_path.name, len(content))
                return content
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"response_{request_id}.json のJSONパースに失敗: {e}"
                ) from e
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(
        f"[debug_ipc] タイムアウト: {response_path.name} が {timeout}秒以内に出現しませんでした。"
        f"\n足軽は以下のファイルを確認して応答を書いてください:\n"
        f"  リクエスト: {DEBUG_DIR / f'request_{request_id}.json'}\n"
        f"  レスポンス: {DEBUG_DIR / f'response_{request_id}.json'}"
    )


def call_debug_llm(
    stage: str,
    system_prompt: str,
    user_prompt: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """
    write_request + wait_for_response のショートカット。

    Args:
        stage: "m3" または "m4"
        system_prompt: システムプロンプト
        user_prompt: ユーザープロンプト
        timeout: タイムアウト秒数

    Returns:
        足軽が応答した content 文字列
    """
    request_id = write_request(stage=stage, system_prompt=system_prompt, user_prompt=user_prompt)
    return wait_for_response(request_id=request_id, timeout=timeout)


# ─────────────────────────────────────────────────────────
# バッチ IPC 関数（cmd_360k_a7e）
# ─────────────────────────────────────────────────────────

def write_batch_request(
    stage: str,
    system_prompt: str,
    items: list[dict],
    request_id: str | None = None,
) -> str:
    """
    バッチリクエスト JSON を /tmp/disclosure_debug/request_{id}.json に書き出す。

    Args:
        stage: "m3" または "m4"
        system_prompt: 全itemに共通のシステムプロンプト
        items: [{"index": 0, "user_prompt": "..."}, ...] のリスト
        request_id: UUID 文字列（None の場合は自動生成）

    Returns:
        request_id（UUID 文字列）
    """
    ensure_debug_dir()
    request_id = request_id or str(uuid4())
    payload = {
        "id": request_id,
        "stage": stage,
        "system_prompt": system_prompt,
        "items": items,
        "batch": True,
        "item_count": len(items),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    request_path = DEBUG_DIR / f"request_{request_id}.json"
    request_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_status(request_id, "pending")
    logger.info(
        "[debug_ipc] バッチリクエスト書き出し: %s (stage=%s, items=%d件)",
        request_path.name, stage, len(items),
    )
    return request_id


def wait_for_batch_response(
    request_id: str,
    timeout: float = BATCH_TIMEOUT,
) -> list[dict]:
    """
    バッチ response_{id}.json が出現するまでポーリングし、results を返す。

    Args:
        request_id: write_batch_request() が返した UUID
        timeout: タイムアウト秒数（デフォルト 600 秒）

    Returns:
        [{"index": 0, "content": "..."}, ...] のリスト

    Raises:
        TimeoutError: timeout 秒以内に応答がない場合
        ValueError: response JSON のパースに失敗した場合、または results キーがない場合
    """
    response_path = DEBUG_DIR / f"response_{request_id}.json"
    deadline = time.monotonic() + timeout
    logger.info(
        "[debug_ipc] バッチ応答待機中: %s (タイムアウト=%ds)",
        response_path.name, int(timeout),
    )

    while time.monotonic() < deadline:
        if response_path.exists():
            try:
                data = json.loads(response_path.read_text(encoding="utf-8"))
                results = data.get("results")
                if results is None:
                    raise ValueError(
                        f"response_{request_id}.json に 'results' キーがありません: {data}"
                    )
                if not isinstance(results, list):
                    raise ValueError(
                        f"response_{request_id}.json の 'results' がリストではありません: {type(results)}"
                    )
                write_status(request_id, "done")
                logger.info(
                    "[debug_ipc] バッチ応答受信: %s (%d件)",
                    response_path.name, len(results),
                )
                return results
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"response_{request_id}.json のJSONパースに失敗: {e}"
                ) from e
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(
        f"[debug_ipc] バッチタイムアウト: {response_path.name} が {timeout}秒以内に出現しませんでした。\n"
        f"足軽は以下のファイルを確認して results[] を含む response を書いてください:\n"
        f"  リクエスト: {DEBUG_DIR / f'request_{request_id}.json'}\n"
        f"  レスポンス: {DEBUG_DIR / f'response_{request_id}.json'}"
    )


def call_debug_llm_batch(
    stage: str,
    system_prompt: str,
    items: list[dict],
    timeout: float = BATCH_TIMEOUT,
) -> list[dict]:
    """
    write_batch_request + wait_for_batch_response のショートカット。

    Args:
        stage: "m3" または "m4"
        system_prompt: システムプロンプト
        items: [{"index": 0, "user_prompt": "..."}, ...]
        timeout: タイムアウト秒数（デフォルト 600 秒）

    Returns:
        [{"index": 0, "content": "..."}, ...] のリスト
    """
    request_id = write_batch_request(stage=stage, system_prompt=system_prompt, items=items)
    return wait_for_batch_response(request_id=request_id, timeout=timeout)
