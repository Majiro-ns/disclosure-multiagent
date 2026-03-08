"""test_debug_mode.py
====================
disclosure-multiagent debug mode バックエンドのテスト。

テスト項目:
  TC-1:  debug_ipc.write_request() が request_{uuid}.json を書き出すこと
  TC-2:  write_request() の JSON に必須キーが含まれること
  TC-3:  debug_ipc.wait_for_response() がレスポンスファイルを読めること
  TC-4:  wait_for_response() がファイル不在の場合 TimeoutError を送出すること
  TC-5:  call_debug_llm() がwrite+waitを正しく呼ぶこと（モック）
  TC-6:  judge_gap() に use_debug=True を渡すと IPC 呼び出しが行われること（モック）
  TC-7:  analyze_gaps() に use_debug=True を渡すと judge_gap に伝搬すること（モック）
  TC-8:  generate_proposal() に use_debug=True を渡すと IPC 呼び出しが行われること（モック）
  TC-9:  generate_proposals() に use_debug=True を渡すと伝搬すること（モック）
  TC-10: 環境変数 USE_DEBUG_LLM=true で analyze_gaps() が debug モードになること
  TC-11: wait_for_response() がレスポンス内の content を正しく返すこと
  TC-12: response JSON に content がない場合 ValueError を送出すること

実行方法（プロジェクトルートから）:
    python3 -m pytest scripts/test_debug_mode.py -v

作成者: Majiro-ns / 2026-03-14 / cmd_360k_a7d
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# scripts/ を sys.path に追加（conftest.py と同等の効果）
sys.path.insert(0, str(Path(__file__).parent))

import debug_ipc
from debug_ipc import (
    DEBUG_DIR,
    call_debug_llm,
    wait_for_response,
    write_request,
)


# ===========================================================================
# 1. debug_ipc ユーティリティのテスト
# ===========================================================================

class TestWriteRequest(unittest.TestCase):
    """write_request() のテスト。"""

    def setUp(self):
        debug_ipc.DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    def test_tc1_creates_request_file(self):
        """TC-1: request_{uuid}.json が作成されること。"""
        req_id = write_request(stage="m3", system_prompt="sys", user_prompt="user")
        request_path = DEBUG_DIR / f"request_{req_id}.json"
        self.assertTrue(request_path.exists(), f"request file が存在しない: {request_path}")
        request_path.unlink(missing_ok=True)  # クリーンアップ

    def test_tc2_request_file_has_required_keys(self):
        """TC-2: request JSON に必須キーが含まれること。"""
        req_id = write_request(stage="m4", system_prompt="sys_p", user_prompt="user_p")
        request_path = DEBUG_DIR / f"request_{req_id}.json"
        data = json.loads(request_path.read_text(encoding="utf-8"))
        self.assertEqual(data["id"], req_id)
        self.assertEqual(data["stage"], "m4")
        self.assertEqual(data["system_prompt"], "sys_p")
        self.assertEqual(data["user_prompt"], "user_p")
        self.assertIn("created_at", data)
        request_path.unlink(missing_ok=True)

    def test_tc2b_request_id_can_be_specified(self):
        """TC-2b: request_id を指定した場合、そのIDが使われること。"""
        req_id = write_request(stage="m3", system_prompt="s", user_prompt="u",
                               request_id="test-fixed-id")
        self.assertEqual(req_id, "test-fixed-id")
        (DEBUG_DIR / f"request_{req_id}.json").unlink(missing_ok=True)


class TestWaitForResponse(unittest.TestCase):
    """wait_for_response() のテスト。"""

    def setUp(self):
        debug_ipc.DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    def test_tc3_reads_response_content(self):
        """TC-3: response_{uuid}.json を読んで content を返すこと。"""
        req_id = "test-read-response"
        response_path = DEBUG_DIR / f"response_{req_id}.json"
        response_path.write_text(
            json.dumps({"id": req_id, "content": "テスト応答テキスト", "created_at": "2026-01-01T00:00:00Z"}),
            encoding="utf-8",
        )
        result = wait_for_response(req_id, timeout=5.0)
        self.assertEqual(result, "テスト応答テキスト")
        response_path.unlink(missing_ok=True)

    def test_tc4_raises_timeout_error(self):
        """TC-4: タイムアウト内にファイルが出現しない場合 TimeoutError を送出すること。"""
        with self.assertRaises(TimeoutError):
            wait_for_response("nonexistent-uuid-xxxx", timeout=0.5)

    def test_tc11_returns_correct_content(self):
        """TC-11: content フィールドの値を正確に返すこと。"""
        req_id = "test-content-exact"
        response_path = DEBUG_DIR / f"response_{req_id}.json"
        expected = '{"has_gap": true, "confidence": "high", "summary": "テスト"}'
        response_path.write_text(
            json.dumps({"id": req_id, "content": expected}), encoding="utf-8"
        )
        result = wait_for_response(req_id, timeout=5.0)
        self.assertEqual(result, expected)
        response_path.unlink(missing_ok=True)

    def test_tc12_raises_value_error_if_no_content(self):
        """TC-12: response JSON に content がない場合 ValueError を送出すること。"""
        req_id = "test-no-content"
        response_path = DEBUG_DIR / f"response_{req_id}.json"
        response_path.write_text(json.dumps({"id": req_id}), encoding="utf-8")
        with self.assertRaises(ValueError):
            wait_for_response(req_id, timeout=5.0)
        response_path.unlink(missing_ok=True)


class TestCallDebugLlm(unittest.TestCase):
    """call_debug_llm() のテスト（モック）。"""

    def test_tc5_calls_write_and_wait(self):
        """TC-5: write_request と wait_for_response を正しく呼ぶこと。"""
        with patch("debug_ipc.write_request", return_value="mock-uuid") as mock_write, \
             patch("debug_ipc.wait_for_response", return_value="応答テキスト") as mock_wait:
            result = call_debug_llm(stage="m3", system_prompt="sys", user_prompt="user")
            mock_write.assert_called_once_with(stage="m3", system_prompt="sys", user_prompt="user")
            mock_wait.assert_called_once_with(request_id="mock-uuid", timeout=debug_ipc.DEFAULT_TIMEOUT)
            self.assertEqual(result, "応答テキスト")


# ===========================================================================
# 2. M3 use_debug フラグのテスト
# ===========================================================================

class TestM3DebugMode(unittest.TestCase):
    """M3 judge_gap() / analyze_gaps() の use_debug フラグテスト。"""

    def setUp(self):
        # 環境変数をリセット
        os.environ.pop("USE_DEBUG_LLM", None)
        os.environ.pop("USE_MOCK_LLM", None)

    def test_tc6_judge_gap_use_debug_calls_ipc(self):
        """TC-6: judge_gap(use_debug=True) が IPC 経由の呼び出しを行うこと。"""
        from m3_gap_analysis_agent import judge_gap, SectionData, LawEntry

        mock_section = MagicMock(spec=SectionData)
        mock_section.heading = "テストセクション"
        mock_section.text = "テキスト"
        mock_section.section_id = "SEC-001"
        mock_entry = MagicMock(spec=LawEntry)
        mock_entry.id = "TEST-001"
        mock_entry.summary = "テスト法令"
        mock_entry.effective_date = None

        mock_response = json.dumps({
            "has_gap": True,
            "confidence": "high",
            "summary": "テストギャップ",
        })

        with patch("debug_ipc.call_debug_llm", return_value=mock_response) as mock_ipc, \
             patch("m3_gap_analysis_agent._build_user_prompt", return_value="prompt"):
            result, in_tok, out_tok = judge_gap(
                section=mock_section,
                disclosure_item="テスト項目",
                law_entry=mock_entry,
                client=None,
                use_debug=True,
            )
            mock_ipc.assert_called_once()
            self.assertEqual(in_tok, 0)
            self.assertEqual(out_tok, 0)
            self.assertTrue(result.get("has_gap"))

    def test_tc7_analyze_gaps_propagates_use_debug(self):
        """TC-7: analyze_gaps(use_debug=True) が judge_gap に use_debug=True を渡すこと。"""
        from m3_gap_analysis_agent import analyze_gaps

        with patch("m3_gap_analysis_agent.judge_gap") as mock_judge:
            mock_judge.return_value = (
                {"has_gap": False, "confidence": "high", "summary": "OK"},
                0, 0,
            )
            mock_report = MagicMock()
            mock_report.sections = [MagicMock()]
            mock_report.document_id = "TEST"
            mock_report.fiscal_year = 2025

            mock_law = MagicMock()
            entry = MagicMock()
            entry.disclosure_items = ["項目A"]
            entry.id = "LAW-001"
            mock_law.applicable_entries = [entry]

            with patch("m3_gap_analysis_agent.is_relevant_section", return_value=True):
                analyze_gaps(mock_report, mock_law, use_debug=True)

            # judge_gap が use_debug=True で呼ばれたか確認
            for call in mock_judge.call_args_list:
                self.assertTrue(call.kwargs.get("use_debug", False))

    def test_tc10_env_var_activates_debug_mode(self):
        """TC-10: 環境変数 USE_DEBUG_LLM=true で debug モードが有効になること。"""
        os.environ["USE_DEBUG_LLM"] = "true"
        from m3_gap_analysis_agent import analyze_gaps

        with patch("m3_gap_analysis_agent.judge_gap") as mock_judge:
            mock_judge.return_value = (
                {"has_gap": False, "confidence": "high", "summary": "OK"},
                0, 0,
            )
            mock_report = MagicMock()
            mock_report.sections = [MagicMock()]
            mock_report.document_id = "TEST"
            mock_report.fiscal_year = 2025

            mock_law = MagicMock()
            entry = MagicMock()
            entry.disclosure_items = ["項目A"]
            entry.id = "LAW-001"
            mock_law.applicable_entries = [entry]

            with patch("m3_gap_analysis_agent.is_relevant_section", return_value=True):
                analyze_gaps(mock_report, mock_law)  # use_debug=None -> 環境変数で解決

            for call in mock_judge.call_args_list:
                self.assertTrue(call.kwargs.get("use_debug", False))

        os.environ.pop("USE_DEBUG_LLM", None)


# ===========================================================================
# 3. M4 use_debug フラグのテスト
# ===========================================================================

class TestM4DebugMode(unittest.TestCase):
    """M4 generate_proposal() / generate_proposals() の use_debug フラグテスト。"""

    def setUp(self):
        os.environ.pop("USE_DEBUG_LLM", None)
        os.environ.pop("USE_MOCK_LLM", None)
        os.environ["ANTHROPIC_API_KEY"] = "dummy-key-for-test"

    def tearDown(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("USE_DEBUG_LLM", None)

    def test_tc8_generate_proposal_use_debug_calls_ipc(self):
        """TC-8: generate_proposal(use_debug=True) が IPC 経由の呼び出しを行うこと。"""
        from m4_proposal_agent import generate_proposal

        with patch("debug_ipc.call_debug_llm", return_value="生成された文案テキスト") as mock_ipc:
            result = generate_proposal(
                section_name="人的資本",
                change_type="追加必須",
                law_summary="人的資本開示義務化",
                law_id="hc-2024-001",
                level="竹",
                use_debug=True,
            )
            mock_ipc.assert_called_once()
            call_kwargs = mock_ipc.call_args.kwargs
            self.assertEqual(call_kwargs["stage"], "m4")
            self.assertEqual(result, "生成された文案テキスト")

    def test_tc9_generate_proposals_propagates_use_debug(self):
        """TC-9: generate_proposals(use_debug=True) が generate_with_quality_check に伝搬すること。"""
        from m4_proposal_agent import generate_proposals, GapItem

        gap = GapItem(
            gap_id="GAP-001",
            section_id="SEC-001",
            has_gap=True,
            disclosure_item="人的資本方針",
            section_heading="人的資本",
            change_type="追加必須",
            reference_law_id="hc-2024-001",
            reference_law_title="人的資本ガイドライン",
            reference_url=None,
            source_confirmed=True,
            source_warning=None,
            law_summary="人的資本開示",
        )

        with patch("m4_proposal_agent.generate_with_quality_check") as mock_check:
            from m4_proposal_agent import Proposal, QualityCheckResult
            mock_proposal = Proposal(
                level="竹", text="文案", quality=QualityCheckResult(passed=True, should_regenerate=False),
                attempts=1, status="pass", placeholders=[],
            )
            mock_check.return_value = mock_proposal

            generate_proposals(gap, use_debug=True)

            for call in mock_check.call_args_list:
                self.assertTrue(call.kwargs.get("use_debug", False))


if __name__ == "__main__":
    unittest.main()
