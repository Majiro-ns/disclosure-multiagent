"""
test_step_execute.py
====================
cmd_360k_a2d: ステップ実行API テスト

テスト仕様（cmd_360k_a2d 要件定義より）:
  TEST 1: create_task_step() がステップモードタスクを作成する
  TEST 2: serialize_step_output() が各ステージのdictを正しく返す
  TEST 3: POST /api/step/start がtask_idとM1出力サマリを返す
  TEST 4: POST /api/step/start → /api/step/{id}/next × 4 で全ステージ完走
  TEST 5: GET /api/step/{task_id}/output/{stage} が正しく中間出力を返す
  TEST 6: POST /api/step/{task_id}/run-all が残りステージを一気に実行する
  TEST 7: エラーハンドリング（404, 422）

USE_MOCK_LLM=true 必須（実LLM APIキー不要）。
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

# USE_MOCK_LLM=true を強制（テスト時に実API呼び出しをしない）
os.environ.setdefault("USE_MOCK_LLM", "true")

# scripts/ + project_root をパスに追加
_SCRIPTS_DIR = Path(__file__).parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# サンプルPDFのパス（M1実行テスト用）
_SAMPLES_DIR = _PROJECT_ROOT / "10_Research" / "samples"
_FIXTURES_DIR = _PROJECT_ROOT / "tests" / "fixtures"
SAMPLE_PDF = _SAMPLES_DIR / "company_a.pdf"
if not SAMPLE_PDF.exists():
    SAMPLE_PDF = _FIXTURES_DIR / "sample_yuho.pdf"
PDF_AVAILABLE = SAMPLE_PDF.exists()


# ═══════════════════════════════════════════════════════════════
# TEST 1: create_task_step() がステップモードタスクを作成する
# ═══════════════════════════════════════════════════════════════

class TestCreateTaskStep(unittest.TestCase):
    """TEST 1: create_task_step() の基本動作確認"""

    def test_creates_task_with_step_mode(self):
        """create_task_step() が execution_mode="step" のタスクを作成する"""
        from api.services.pipeline import create_task_step, get_task

        task_id = create_task_step(
            pdf_path="/tmp/test.pdf",
            company_name="テスト株式会社",
            fiscal_year=2025,
            fiscal_month_end=3,
            level="竹",
            use_mock=True,
        )

        task = get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task.execution_mode, "step")
        self.assertEqual(task.next_stage, "m1")
        self.assertEqual(task.status, "queued")

    def test_task_has_5_pending_steps(self):
        """初期状態で5ステップ全てが pending"""
        from api.services.pipeline import create_task_step, get_task

        task_id = create_task_step(
            pdf_path="/tmp/test.pdf",
            company_name="テスト株式会社",
            fiscal_year=2025,
            fiscal_month_end=3,
            level="竹",
            use_mock=True,
        )
        task = get_task(task_id)
        self.assertEqual(len(task.steps), 5)
        for step in task.steps:
            self.assertEqual(step.status, "pending")

    def test_task_id_is_8_chars(self):
        """task_id は8文字の文字列"""
        from api.services.pipeline import create_task_step

        task_id = create_task_step(
            pdf_path="/tmp/test.pdf",
            company_name="テスト株式会社",
            fiscal_year=2025,
            fiscal_month_end=3,
            level="竹",
            use_mock=True,
        )
        self.assertIsInstance(task_id, str)
        self.assertEqual(len(task_id), 8)


# ═══════════════════════════════════════════════════════════════
# TEST 2: serialize_step_output() が各ステージのdictを正しく返す
# ═══════════════════════════════════════════════════════════════

class TestSerializeStepOutput(unittest.TestCase):
    """TEST 2: serialize_step_output() の出力フィールド確認"""

    def _make_mock_m1_report(self):
        """M1用モックオブジェクト（SimpleNamespace でdataclassを代替）"""
        section = SimpleNamespace(
            section_id="s1",
            heading="人的資本",
            text="テストテキスト" * 50,
        )
        return SimpleNamespace(
            sections=[section],
            company_name="テスト株式会社",
            fiscal_year=2025,
            document_id="doc-test-001",
        )

    def _make_mock_m2_law_context(self):
        """M2用モックオブジェクト"""
        entry = SimpleNamespace(id="law-001", title="改正法令A", category="人的資本")
        return SimpleNamespace(
            applicable_entries=[entry],
            warnings=["WARN-001"],
            missing_categories=[],
        )

    def _make_mock_m3_gap_result(self):
        """M3用モックオブジェクト"""
        gap = SimpleNamespace(
            gap_id="gap-001",
            section_heading="人的資本",
            change_type="追加",
            has_gap=True,
            gap_description="開示不足",
            disclosure_item="多様性推進",
            confidence="high",
        )
        return SimpleNamespace(
            summary=SimpleNamespace(total_gaps=1, by_change_type={"追加": 1}),
            gaps=[gap],
        )

    def _make_mock_m4_proposals(self):
        """M4用モックオブジェクト"""
        proposal = SimpleNamespace(
            gap_id="gap-001",
            disclosure_item="多様性推進",
            matsu=SimpleNamespace(text="松: 詳細な開示文章" * 5),
            take=SimpleNamespace(text="竹: 標準的な開示文章" * 5),
            ume=SimpleNamespace(text="梅: 簡潔な開示文章" * 5),
        )
        return [proposal]

    def test_m1_output_has_required_fields(self):
        """M1シリアライズ → sections_count, company_name, sections が含まれる"""
        from api.services.pipeline import serialize_step_output

        output = serialize_step_output("m1", self._make_mock_m1_report())
        self.assertIn("sections_count", output)
        self.assertIn("company_name", output)
        self.assertIn("sections", output)
        self.assertEqual(output["sections_count"], 1)
        self.assertEqual(len(output["sections"]), 1)
        self.assertIn("text_snippet", output["sections"][0])

    def test_m2_output_has_required_fields(self):
        """M2シリアライズ → applicable_entries_count, entries が含まれる"""
        from api.services.pipeline import serialize_step_output

        output = serialize_step_output("m2", self._make_mock_m2_law_context())
        self.assertIn("applicable_entries_count", output)
        self.assertIn("entries", output)
        self.assertIn("warnings", output)
        self.assertEqual(output["applicable_entries_count"], 1)

    def test_m3_output_has_required_fields(self):
        """M3シリアライズ → total_gaps, gaps が含まれる"""
        from api.services.pipeline import serialize_step_output

        output = serialize_step_output("m3", self._make_mock_m3_gap_result())
        self.assertIn("total_gaps", output)
        self.assertIn("gaps", output)
        self.assertEqual(output["total_gaps"], 1)
        self.assertEqual(len(output["gaps"]), 1)
        gap = output["gaps"][0]
        self.assertIn("gap_id", gap)
        self.assertIn("has_gap", gap)
        self.assertIn("description", gap)

    def test_m4_output_has_required_fields(self):
        """M4シリアライズ → proposals_count, proposals が含まれる"""
        from api.services.pipeline import serialize_step_output

        output = serialize_step_output("m4", self._make_mock_m4_proposals())
        self.assertIn("proposals_count", output)
        self.assertIn("proposals", output)
        self.assertEqual(output["proposals_count"], 1)
        p = output["proposals"][0]
        self.assertIn("gap_id", p)
        self.assertIn("matsu_snippet", p)
        self.assertIn("take_snippet", p)
        self.assertIn("ume_snippet", p)

    def test_m5_output_has_report_markdown(self):
        """M5シリアライズ → report_markdown, char_count が含まれる"""
        from api.services.pipeline import serialize_step_output

        report_text = "# テストレポート\n\n## 1. 概要\n\n内容" * 10
        output = serialize_step_output("m5", report_text)
        self.assertIn("report_markdown", output)
        self.assertIn("char_count", output)
        self.assertEqual(output["char_count"], len(report_text))
        self.assertEqual(output["report_markdown"], report_text)

    def test_unknown_stage_returns_empty_dict(self):
        """不明なステージは空dictを返す"""
        from api.services.pipeline import serialize_step_output

        output = serialize_step_output("m99", "dummy")
        self.assertEqual(output, {})


# ═══════════════════════════════════════════════════════════════
# TEST 3-7: APIエンドポイント（TestClient 使用）
# ═══════════════════════════════════════════════════════════════

@unittest.skipUnless(PDF_AVAILABLE, f"サンプルPDFが存在しません: {SAMPLE_PDF}")
class TestStepAPIEndpoints(unittest.TestCase):
    """TEST 3-7: POST /api/step/* エンドポイントの統合テスト"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from api.main import app
        cls.client = TestClient(app)
        cls.pdf_path = str(SAMPLE_PDF)

    def _start_step(self) -> dict:
        """POST /api/step/start を実行し、レスポンスdictを返す。"""
        response = self.client.post("/api/step/start", json={
            "pdf_path": self.pdf_path,
            "company_name": "テスト株式会社",
            "fiscal_year": 2025,
            "fiscal_month_end": 3,
            "level": "竹",
            "use_mock": True,
        })
        self.assertEqual(response.status_code, 200, f"start failed: {response.text}")
        return response.json()

    def test_step_start_returns_task_id_and_m1_output(self):
        """TEST 3: POST /api/step/start がtask_idとM1出力サマリを返す"""
        data = self._start_step()
        self.assertIn("task_id", data)
        self.assertIn("m1_output", data)
        self.assertIn("next_stage", data)
        self.assertEqual(data["next_stage"], "m2")
        m1 = data["m1_output"]
        self.assertIn("sections_count", m1)
        self.assertIn("company_name", m1)

    def test_step_next_completes_all_stages(self):
        """TEST 4: /start → /next x 4 で全ステージ完走し status=all_done"""
        start_data = self._start_step()
        task_id = start_data["task_id"]

        # M2, M3, M4, M5 を順に実行
        expected_stages = ["m2", "m3", "m4", "m5"]
        for i, expected_stage in enumerate(expected_stages):
            resp = self.client.post(f"/api/step/{task_id}/next")
            self.assertEqual(resp.status_code, 200, f"Step {i+1} ({expected_stage}) failed: {resp.text}")
            data = resp.json()
            self.assertEqual(data["step"], expected_stage, f"Expected step={expected_stage}")
            if i < 3:
                self.assertEqual(data["status"], "done")
                self.assertIsNotNone(data["next_stage"])
            else:
                # M5完了
                self.assertEqual(data["status"], "all_done")
                self.assertIsNone(data["next_stage"])

    def test_get_step_output_returns_m1_detail(self):
        """TEST 5a: GET /api/step/{task_id}/output/m1 がM1詳細出力を返す"""
        start_data = self._start_step()
        task_id = start_data["task_id"]

        resp = self.client.get(f"/api/step/{task_id}/output/m1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["stage"], "m1")
        self.assertEqual(data["task_id"], task_id)
        self.assertIn("sections_count", data["output"])
        self.assertIn("sections", data["output"])

    def test_get_step_output_after_all_stages(self):
        """TEST 5b: 全ステージ完了後、各ステージの出力が取得できる"""
        start_data = self._start_step()
        task_id = start_data["task_id"]

        # 残りを全実行
        self.client.post(f"/api/step/{task_id}/run-all")

        for stage in ["m1", "m2", "m3", "m4", "m5"]:
            resp = self.client.get(f"/api/step/{task_id}/output/{stage}")
            self.assertEqual(resp.status_code, 200, f"output/{stage} failed")
            data = resp.json()
            self.assertEqual(data["stage"], stage)
            self.assertIsInstance(data["output"], dict)

    def test_step_run_all_completes_remaining_stages(self):
        """TEST 6: POST /api/step/{task_id}/run-all が残りステージを全て実行する"""
        start_data = self._start_step()
        task_id = start_data["task_id"]

        # M1完了後に run-all（M2-M5を一気に実行）
        resp = self.client.post(f"/api/step/{task_id}/run-all")
        self.assertEqual(resp.status_code, 200, f"run-all failed: {resp.text}")
        data = resp.json()
        self.assertEqual(data["status"], "done")
        self.assertEqual(data["next_stage"], "done")
        self.assertIsNotNone(data["result"])
        # 最終レポートが含まれる
        self.assertIn("report_markdown", data["result"])

    def test_step_run_all_from_middle(self):
        """TEST 6b: M2まで進めてから run-all（M3-M5を一気に実行）"""
        start_data = self._start_step()
        task_id = start_data["task_id"]

        # M2を先に実行
        self.client.post(f"/api/step/{task_id}/next")  # M2

        # run-all（M3-M5）
        resp = self.client.post(f"/api/step/{task_id}/run-all")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "done")

    def test_next_on_completed_task_returns_422(self):
        """TEST 7a: 全ステージ完了後に /next を呼ぶと 422 が返る"""
        start_data = self._start_step()
        task_id = start_data["task_id"]
        self.client.post(f"/api/step/{task_id}/run-all")

        resp = self.client.post(f"/api/step/{task_id}/next")
        self.assertEqual(resp.status_code, 422)

    def test_next_on_unknown_task_returns_404(self):
        """TEST 7b: 存在しないタスクIDで /next を呼ぶと 404 が返る"""
        resp = self.client.post("/api/step/nonexistent/next")
        self.assertEqual(resp.status_code, 404)

    def test_output_on_unexecuted_stage_returns_404(self):
        """TEST 7c: まだ実行していないステージの出力を取得すると 404"""
        start_data = self._start_step()
        task_id = start_data["task_id"]
        # M1は実行済み、M2はまだ
        resp = self.client.get(f"/api/step/{task_id}/output/m2")
        self.assertEqual(resp.status_code, 404)

    def test_output_invalid_stage_returns_422(self):
        """TEST 7d: 不正なステージ名で /output/{stage} を呼ぶと 422 が返る"""
        start_data = self._start_step()
        task_id = start_data["task_id"]
        resp = self.client.get(f"/api/step/{task_id}/output/invalid_stage")
        self.assertEqual(resp.status_code, 422)

    def test_run_all_on_completed_task_returns_422(self):
        """TEST 7e: 全完了済みタスクに run-all を呼ぶと 422"""
        start_data = self._start_step()
        task_id = start_data["task_id"]
        self.client.post(f"/api/step/{task_id}/run-all")

        resp = self.client.post(f"/api/step/{task_id}/run-all")
        self.assertEqual(resp.status_code, 422)


# ═══════════════════════════════════════════════════════════════
# PDF不要テスト（スキップされない）
# ═══════════════════════════════════════════════════════════════

class TestStepAPINoPDF(unittest.TestCase):
    """PDF不要のAPIエラーハンドリングテスト"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from api.main import app
        cls.client = TestClient(app)

    def test_start_with_nonexistent_pdf_returns_500(self):
        """存在しないPDFパスで /start を呼ぶと 500 が返る（M1失敗）"""
        resp = self.client.post("/api/step/start", json={
            "pdf_path": "/tmp/nonexistent_test_pdf_abc123.pdf",
            "company_name": "テスト株式会社",
            "fiscal_year": 2025,
            "fiscal_month_end": 3,
            "level": "竹",
            "use_mock": True,
        })
        self.assertEqual(resp.status_code, 500)

    def test_next_on_nonexistent_task_returns_404(self):
        """存在しないタスクで /next → 404"""
        resp = self.client.post("/api/step/does-not-exist/next")
        self.assertEqual(resp.status_code, 404)

    def test_run_all_on_nonexistent_task_returns_404(self):
        """存在しないタスクで /run-all → 404"""
        resp = self.client.post("/api/step/does-not-exist/run-all")
        self.assertEqual(resp.status_code, 404)

    def test_output_on_nonexistent_task_returns_404(self):
        """存在しないタスクで /output/m1 → 404"""
        resp = self.client.get("/api/step/does-not-exist/output/m1")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
