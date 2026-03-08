#!/usr/bin/env python3
"""
debug_monitor.py — disclosure debug mode モニター

使い方:
  python3 scripts/debug_monitor.py           # インタラクティブモード（手入力）
  python3 scripts/debug_monitor.py --auto    # 自動モード（足軽がWriteツールで書き込む）

仕組み:
  /tmp/disclosure_debug/ を監視
  request_{id}.json を検知 → system_prompt + user_prompt/items を表示
  インタラクティブモード: 応答を標準入力から受け取り response_{id}.json に書く
  自動モード: request 内容を表示してポーズ（足軽が response_{id}.json を直接書く）

【単件 response_{id}.json フォーマット】
  {"id": "uuid", "content": "応答テキスト", "created_at": "ISO8601"}

【バッチ response_{id}.json フォーマット】（batch: true の場合）
  {"id": "uuid", "results": [{"index": 0, "content": "..."}, ...], "created_at": "ISO8601"}

cmd_360k_a7d: 単件IPC対応 (2026-03-14)
cmd_360k_a7e: バッチIPC対応追加 (2026-03-14)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# debug_ipc のステータス関数を使えるなら使う（インポート失敗時は無視）
try:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    from debug_ipc import write_status as _write_status
except ImportError:
    _write_status = None  # type: ignore

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


def is_batch_request(data: dict) -> bool:
    """バッチリクエストか否かを判定する。"""
    return bool(data.get("batch"))


def display_request(req_path: Path) -> dict:
    """リクエストの内容を読み込んで表示する。内容を返す。"""
    with open(req_path, encoding="utf-8") as f:
        data = json.load(f)

    rid = req_path.stem.replace("request_", "")
    ts = datetime.now().strftime("%H:%M:%S")
    batch = is_batch_request(data)
    mode_label = "【バッチ】" if batch else "【単件】"

    print("\n" + "=" * 60)
    print(f"[{ts}] 📩 {mode_label}リクエスト検知: {req_path.name}")
    print(f"  ID: {rid}  stage: {data.get('stage', '?')}")
    if batch:
        print(f"  items: {data.get('item_count', len(data.get('items', [])))}件")
    print("=" * 60)

    if "system_prompt" in data:
        sp = data["system_prompt"]
        print("\n--- SYSTEM PROMPT ---")
        print(sp[:500] + ("..." if len(sp) > 500 else ""))

    if batch and "items" in data:
        print(f"\n--- BATCH ITEMS ({len(data['items'])}件) ---")
        for item in data["items"]:
            idx = item.get("index", "?")
            up = item.get("user_prompt", "")
            print(f"\n[index={idx}]\n{up[:400]}{'...' if len(up) > 400 else ''}")
    elif "user_prompt" in data:
        print("\n--- USER PROMPT ---")
        print(data["user_prompt"])

    if "messages" in data:
        print("\n--- MESSAGES ---")
        for msg in data["messages"]:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            print(f"[{role}] {content}")

    # ステータスを "processing" に更新
    if _write_status is not None:
        try:
            _write_status(rid, "processing")
        except Exception:
            pass

    print("\n" + "-" * 60)
    return data


def write_response(rid: str, response_text: str, metadata: dict | None = None) -> Path:
    """単件 response_{id}.json を書き込む。"""
    resp_path = WATCH_DIR / f"response_{rid}.json"
    payload = {
        "id": rid,
        "content": response_text,  # debug_ipc.wait_for_response() が "content" キーを期待
        "timestamp": datetime.now().isoformat(),
    }
    if metadata:
        payload.update(metadata)
    with open(resp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return resp_path


def write_batch_response(rid: str, results: list[dict]) -> Path:
    """バッチ response_{id}.json を書き込む。"""
    resp_path = WATCH_DIR / f"response_{rid}.json"
    payload = {
        "id": rid,
        "results": results,  # debug_ipc.wait_for_batch_response() が "results" キーを期待
        "timestamp": datetime.now().isoformat(),
    }
    with open(resp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return resp_path


def _read_multiline_input(prompt: str = "") -> str:
    """複数行の入力を受け取る（空行2回 または 'EOF' で確定）。"""
    if prompt:
        print(prompt)
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "EOF":
            break
        lines.append(line)
        if len(lines) >= 2 and lines[-1] == "" and lines[-2] == "":
            lines = lines[:-2]
            break
    return "\n".join(lines).strip()


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

            if is_batch_request(data):
                # ── バッチリクエスト処理 ──
                items = data.get("items", [])
                print(f"▶ バッチ応答入力 ({len(items)}件)。")
                print("  各itemを 'index,content' 形式で入力（'EOF' で終了）:")
                results = []
                while True:
                    try:
                        line = input()
                    except EOFError:
                        break
                    if line == "EOF":
                        break
                    if "," in line:
                        idx_str, _, content = line.partition(",")
                        try:
                            idx = int(idx_str.strip())
                            results.append({"index": idx, "content": content.strip()})
                        except ValueError:
                            print(f"  ⚠️ 無効な形式: {line}")
                if results:
                    resp_path = write_batch_response(rid, results)
                    print(f"✅ バッチ応答書き込み完了: {resp_path.name} ({len(results)}件)")
                else:
                    print("⚠️ 応答なし — スキップ")
            else:
                # ── 単件リクエスト処理 ──
                response_text = _read_multiline_input(
                    "▶ 応答を入力してください（空行2回で確定 / 'EOF' 単独行で確定）:"
                )
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
            print(f"   以下のファイルを作成してください: {resp_path}")

            if is_batch_request(data):
                items = data.get("items", [])
                print(f"   【バッチ形式】{len(items)}件の結果を以下の形式で書いてください:")
                print(f'   {{"id": "{rid}", "results": [{{"index": 0, "content": "..."}}, ...]}}')
            else:
                print(f'   【単件形式】{{"id": "{rid}", "content": "<応答テキスト>"}}')
            print()

            # 応答ファイルが現れるまで待つ
            while not resp_path.exists():
                time.sleep(POLL_INTERVAL)

            print(f"✅ 応答ファイル検知: {resp_path.name}")
            try:
                with open(resp_path, encoding="utf-8") as f:
                    resp_data = json.load(f)
                if "results" in resp_data:
                    print(f"   バッチ応答: {len(resp_data['results'])}件")
                else:
                    preview = str(resp_data.get("content", ""))[:200]
                    print(f"   応答内容（先頭200文字）: {preview}")
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
