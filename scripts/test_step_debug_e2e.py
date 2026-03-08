"""test_step_debug_e2e.py
========================
disclosure debug mode の E2E 動作確認テスト（cmd_360k_a6d）。

テスト項目:
  ST-1: 単件 IPC フロー（write_request → ステータスpending → 応答 → ステータスdone）
  ST-2: バッチ IPC フロー（write_batch_request → ステータスpending → 応答 → ステータスdone）
  ST-3: debug_monitor の display_request がステータスを processing に更新すること
  ST-4: write_status / read_status の基本動作
  ST-5: ステータス遷移の完全な確認（pending → processing → done）
  ST-6: タイムアウト時にステータスが pending のままであること
  ST-7: バックグラウンドスレッドで応答を書き込んだ場合に wait_for_response が返ること
  ST-8: バッチ応答をバックグラウンドスレッドで書き込んだ場合に wait_for_batch_response が返ること

実行方法（プロジェクトルートから）:
    python3 -m pytest scripts/test_step_debug_e2e.py -v

作成者: Majiro-ns / 2026-03-14 / cmd_360k_a6d
"""
from __future__ import annotations

import json
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import debug_ipc
from debug_ipc import (
    DEBUG_DIR,
    read_status,
    write_status,
    write_request,
    write_batch_request,
    wait_for_response,
    wait_for_batch_response,
)


def _cleanup(*paths: Path) -> None:
    """テスト用ファイルを削除するヘルパー。"""
    for p in paths:
        p.unlink(missing_ok=True)


class TestStatusFunctions(unittest.TestCase):
    """ST-4: write_status / read_status の基本動作テスト。"""

    def setUp(self):
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    def test_st4_write_and_read_status(self):
        """write_status で書いた内容を read_status で読めること。"""
        rid = "st4-status-rw"
        status_path = DEBUG_DIR / f"status_{rid}.json"
        try:
            write_status(rid, "pending")
            self.assertEqual(read_status(rid), "pending")
            write_status(rid, "processing")
            self.assertEqual(read_status(rid), "processing")
            write_status(rid, "done")
            self.assertEqual(read_status(rid), "done")
        finally:
            _cleanup(status_path)

    def test_st4b_read_status_returns_none_if_not_exists(self):
        """ステータスファイルが存在しない場合 None を返すこと。"""
        self.assertIsNone(read_status("nonexistent-st4b-uuid"))


class TestSingleIpcE2E(unittest.TestCase):
    """ST-1, ST-5, ST-6, ST-7: 単件 IPC フローの E2E テスト。"""

    def setUp(self):
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    def test_st1_single_ipc_flow(self):
        """ST-1: write_request → ステータスpending → 応答書込み → wait → ステータスdone。"""
        rid = write_request(stage="m3", system_prompt="sys", user_prompt="ギャップ分析を行え")
        request_path = DEBUG_DIR / f"request_{rid}.json"
        response_path = DEBUG_DIR / f"response_{rid}.json"
        status_path = DEBUG_DIR / f"status_{rid}.json"
        try:
            # pending 状態確認
            self.assertEqual(read_status(rid), "pending", "write_request 直後はpendingであること")

            # 応答ファイルを書き込む（debug_monitor が書く想定）
            response_path.write_text(
                json.dumps({"id": rid, "content": "分析結果テキスト"}), encoding="utf-8"
            )

            # wait_for_response が content を返すこと
            result = wait_for_response(rid, timeout=5.0)
            self.assertEqual(result, "分析結果テキスト")

            # done 状態確認
            self.assertEqual(read_status(rid), "done", "wait_for_response 後はdoneであること")
        finally:
            _cleanup(request_path, response_path, status_path)

    def test_st5_status_transition_pending_to_done(self):
        """ST-5: ステータスが pending → done に遷移すること（processing は外部から更新）。"""
        rid = "st5-transition"
        status_path = DEBUG_DIR / f"status_{rid}.json"
        request_path = DEBUG_DIR / f"request_{rid}.json"
        response_path = DEBUG_DIR / f"response_{rid}.json"
        try:
            # write_request で pending
            rid2 = write_request(stage="m4", system_prompt="sys", user_prompt="提案を生成せよ",
                                  request_id=rid)
            self.assertEqual(read_status(rid2), "pending")

            # debug_monitor が processing にする（手動で更新）
            write_status(rid2, "processing")
            self.assertEqual(read_status(rid2), "processing")

            # 応答を書き込み → wait → done
            response_path.write_text(json.dumps({"id": rid2, "content": "提案テキスト"}), encoding="utf-8")
            wait_for_response(rid2, timeout=5.0)
            self.assertEqual(read_status(rid2), "done")
        finally:
            _cleanup(status_path, request_path, response_path)

    def test_st6_timeout_leaves_status_pending(self):
        """ST-6: タイムアウト時にステータスが pending のままであること。"""
        rid = "st6-timeout"
        status_path = DEBUG_DIR / f"status_{rid}.json"
        request_path = DEBUG_DIR / f"request_{rid}.json"
        response_path = DEBUG_DIR / f"response_{rid}.json"
        try:
            # stale fileがある場合は先にクリア
            response_path.unlink(missing_ok=True)
            write_request(stage="m3", system_prompt="sys", user_prompt="prompt",
                          request_id=rid)
            self.assertEqual(read_status(rid), "pending")
            with self.assertRaises(TimeoutError):
                wait_for_response(rid, timeout=0.3)
            # タイムアウト後もステータスは pending のまま
            self.assertEqual(read_status(rid), "pending")
        finally:
            _cleanup(status_path, request_path, response_path)

    def test_st7_background_thread_response(self):
        """ST-7: バックグラウンドスレッドで応答を書いた場合に wait_for_response が返ること。"""
        rid = "st7-bg-thread"
        request_path = DEBUG_DIR / f"request_{rid}.json"
        response_path = DEBUG_DIR / f"response_{rid}.json"
        status_path = DEBUG_DIR / f"status_{rid}.json"
        try:
            write_request(stage="m3", system_prompt="sys", user_prompt="prompt", request_id=rid)

            def _write_after_delay():
                time.sleep(0.5)
                response_path.write_text(
                    json.dumps({"id": rid, "content": "バックグラウンド応答"}), encoding="utf-8"
                )

            t = threading.Thread(target=_write_after_delay, daemon=True)
            t.start()

            result = wait_for_response(rid, timeout=5.0)
            self.assertEqual(result, "バックグラウンド応答")
            self.assertEqual(read_status(rid), "done")
            t.join(timeout=2.0)
        finally:
            _cleanup(request_path, response_path, status_path)


class TestBatchIpcE2E(unittest.TestCase):
    """ST-2, ST-8: バッチ IPC フローの E2E テスト。"""

    def setUp(self):
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    def test_st2_batch_ipc_flow(self):
        """ST-2: write_batch_request → ステータスpending → 応答書込み → wait → ステータスdone。"""
        items = [
            {"index": 0, "user_prompt": "セクション0を分析せよ"},
            {"index": 1, "user_prompt": "セクション1を分析せよ"},
        ]
        rid = write_batch_request(stage="m3", system_prompt="sys", items=items)
        request_path = DEBUG_DIR / f"request_{rid}.json"
        response_path = DEBUG_DIR / f"response_{rid}.json"
        status_path = DEBUG_DIR / f"status_{rid}.json"
        try:
            # pending 確認
            self.assertEqual(read_status(rid), "pending")

            # バッチ応答を書き込む
            results = [
                {"index": 0, "content": "セクション0の分析結果"},
                {"index": 1, "content": "セクション1の分析結果"},
            ]
            response_path.write_text(
                json.dumps({"id": rid, "results": results}), encoding="utf-8"
            )

            # wait_for_batch_response が results を返すこと
            got = wait_for_batch_response(rid, timeout=5.0)
            self.assertEqual(len(got), 2)
            self.assertEqual(got[0]["content"], "セクション0の分析結果")
            self.assertEqual(got[1]["content"], "セクション1の分析結果")

            # done 状態確認
            self.assertEqual(read_status(rid), "done")
        finally:
            _cleanup(request_path, response_path, status_path)

    def test_st8_batch_background_thread(self):
        """ST-8: バッチ応答をバックグラウンドスレッドで書き込んだ場合に返ること。"""
        items = [{"index": 0, "user_prompt": "prompt0"}]
        rid = write_batch_request(stage="m4", system_prompt="sys", items=items)
        request_path = DEBUG_DIR / f"request_{rid}.json"
        response_path = DEBUG_DIR / f"response_{rid}.json"
        status_path = DEBUG_DIR / f"status_{rid}.json"
        try:
            def _write_batch_after_delay():
                time.sleep(0.5)
                response_path.write_text(
                    json.dumps({"id": rid, "results": [{"index": 0, "content": "バッチBG応答"}]}),
                    encoding="utf-8",
                )

            t = threading.Thread(target=_write_batch_after_delay, daemon=True)
            t.start()

            got = wait_for_batch_response(rid, timeout=5.0)
            self.assertEqual(got[0]["content"], "バッチBG応答")
            self.assertEqual(read_status(rid), "done")
            t.join(timeout=2.0)
        finally:
            _cleanup(request_path, response_path, status_path)


class TestDebugMonitorStatusUpdate(unittest.TestCase):
    """ST-3: debug_monitor の display_request がステータスを processing に更新すること。"""

    def setUp(self):
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    def test_st3_display_request_sets_processing(self):
        """display_request() 呼び出し後にステータスが processing になること。"""
        import debug_monitor
        import io
        from contextlib import redirect_stdout

        rid = "st3-monitor"
        request_path = DEBUG_DIR / f"request_{rid}.json"
        status_path = DEBUG_DIR / f"status_{rid}.json"
        try:
            # request ファイルを書き出し（pending）
            write_request(stage="m3", system_prompt="sys", user_prompt="プロンプト", request_id=rid)
            self.assertEqual(read_status(rid), "pending")

            # display_request を呼ぶ（stdout を抑制）
            with redirect_stdout(io.StringIO()):
                debug_monitor.display_request(request_path)

            # processing になっていること
            self.assertEqual(read_status(rid), "processing")
        finally:
            _cleanup(request_path, status_path)


if __name__ == "__main__":
    unittest.main()
