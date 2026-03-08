#!/usr/bin/env python3
"""
debug_monitor.py — disclosure debug mode モニター

使い方:
  python3 scripts/debug_monitor.py           # インタラクティブモード（手入力）
  python3 scripts/debug_monitor.py --auto    # 自動モード（足軽がWriteツールで書き込む）

仕組み:
  /tmp/disclosure_debug/ を監視
  request_{id}.json を検知 → system_prompt + user_prompt を表示
  インタラクティブモード: 応答を標準入力から受け取り response_{id}.json に書く
  自動モード: request 内容を表示してポーズ（足軽が response_{id}.json を直接書く）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

WATCH_DIR = Path("/tmp/disclosure_debug")
POLL_INTERVAL = 1.0  # seconds


def ensure_dir() -> None:
    WATCH_DIR.mkdir(parents=True, exist_ok=True)


def list_pending_requests() -> list[Path]:
    """未処理の request_{id}.json を返す（response_{id}.json がないもの）"""
    reqs = sorted(WATCH_DIR.glob("request_*.json"))
    pending = []
    for req in reqs:
        rid = req.stem.replace("request_", "")
        resp = WATCH_DIR / f"response_{rid}.json"
        if not resp.exists():
            pending.append(req)
    return pending


def display_request(req_path: Path) -> dict:
    """リクエストの内容を読み込んで表示する。内容を返す。"""
    with open(req_path, encoding="utf-8") as f:
        data = json.load(f)

    rid = req_path.stem.replace("request_", "")
    ts = datetime.now().strftime("%H:%M:%S")

    print("\n" + "=" * 60)
    print(f"[{ts}] 📩 リクエスト検知: {req_path.name}")
    print(f"  ID: {rid}")
    if "agent" in data:
        print(f"  エージェント: {data['agent']}")
    if "model" in data:
        print(f"  モデル: {data['model']}")
    print("=" * 60)

    if "system_prompt" in data:
        print("\n--- SYSTEM PROMPT ---")
        print(data["system_prompt"])

    if "user_prompt" in data:
        print("\n--- USER PROMPT ---")
        print(data["user_prompt"])

    if "messages" in data:
        print("\n--- MESSAGES ---")
        for msg in data["messages"]:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            print(f"[{role}] {content}")

    print("\n" + "-" * 60)
    return data


def write_response(rid: str, response_text: str, metadata: dict | None = None) -> Path:
    """response_{id}.json を書き込む。"""
    resp_path = WATCH_DIR / f"response_{rid}.json"
    payload = {
        "id": rid,
        "response": response_text,
        "timestamp": datetime.now().isoformat(),
    }
    if metadata:
        payload.update(metadata)
    with open(resp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return resp_path


def interactive_mode() -> None:
    """インタラクティブモード: 応答を標準入力から受け取る。"""
    print("🟢 Debug Monitor 起動（インタラクティブモード）")
    print(f"   監視ディレクトリ: {WATCH_DIR}")
    print("   Ctrl+C で終了\n")

    ensure_dir()

    while True:
        pending = list_pending_requests()
        for req_path in pending:
            rid = req_path.stem.replace("request_", "")
            data = display_request(req_path)

            print("▶ 応答を入力してください（空行2回で確定 / 'EOF' 単独行で確定）:")
            lines = []
            while True:
                try:
                    line = input()
                except EOFError:
                    break
                if line == "EOF":
                    break
                lines.append(line)
                # 空行2回で確定
                if len(lines) >= 2 and lines[-1] == "" and lines[-2] == "":
                    lines = lines[:-2]  # 末尾の空行2つは除去
                    break

            response_text = "\n".join(lines).strip()
            if not response_text:
                response_text = "[足軽応答なし]"

            resp_path = write_response(rid, response_text)
            print(f"✅ 応答書き込み完了: {resp_path.name}")

        time.sleep(POLL_INTERVAL)


def auto_mode() -> None:
    """自動モード: リクエストを表示してポーズ。足軽がWriteツールで書き込む。"""
    print("🔵 Debug Monitor 起動（自動モード）")
    print(f"   監視ディレクトリ: {WATCH_DIR}")
    print(f"   応答は response_{{id}}.json を直接 {WATCH_DIR}/ に書き込んでください")
    print("   Ctrl+C で終了\n")

    ensure_dir()
    seen: set[str] = set()

    while True:
        pending = list_pending_requests()
        for req_path in pending:
            rid = req_path.stem.replace("request_", "")
            if rid in seen:
                continue
            seen.add(rid)

            data = display_request(req_path)

            resp_path = WATCH_DIR / f"response_{rid}.json"
            print(f"\n⏸  応答待機中...")
            print(f"   以下のファイルを作成してください:")
            print(f"   {resp_path}")
            print(f'   形式: {{"id": "{rid}", "response": "<応答テキスト>"}}')
            print()

            # 応答ファイルが現れるまで待つ
            while not resp_path.exists():
                time.sleep(POLL_INTERVAL)

            print(f"✅ 応答ファイル検知: {resp_path.name}")
            try:
                with open(resp_path, encoding="utf-8") as f:
                    resp_data = json.load(f)
                print(f"   応答内容（先頭200文字）: {str(resp_data.get('response', ''))[:200]}")
            except Exception as e:
                print(f"   ⚠️  読み込みエラー: {e}")

        time.sleep(POLL_INTERVAL)


def main() -> None:
    parser = argparse.ArgumentParser(description="disclosure debug mode モニター")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="自動モード: リクエストを表示してポーズ（足軽がWriteツールで応答書き込み）",
    )
    args = parser.parse_args()

    try:
        if args.auto:
            auto_mode()
        else:
            interactive_mode()
    except KeyboardInterrupt:
        print("\n\n👋 Debug Monitor 終了")
        sys.exit(0)


if __name__ == "__main__":
    main()
