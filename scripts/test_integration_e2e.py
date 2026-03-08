"""ステップ実行モード E2E 結合テスト（cmd_360k_a8c）。

A2(API) + A3(スキーマ修正) + A4(UI) + A6(debug E2E) + A7(バッチ化)
全員の実装を組み合わせた結合テスト。

テスト構造:
  IT-1: M1→M5 ステップ実行 完走（start→next×4→all_done）
  IT-2: 各ステージの出力スキーマ検証（M1〜M5の必須フィールド）
  IT-3: GET /api/step/{task_id}/output/{stage} 5ステージ全件
  IT-4: run-all: M1 start → run-all で残り一括実行
  IT-5: エラーハンドリング（404/422）
"""
import os
import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)
PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tests", "fixtures", "sample_yuho.pdf"
)
PDF_PATH = os.path.abspath(PDF_PATH)


def _start() -> dict:
    """ステップ実行を開始してレスポンスを返す。"""
    resp = client.post(
        "/api/step/start",
        json={
            "pdf_path": PDF_PATH,
            "company_name": "株式会社テスト商事",
            "fiscal_year": 2025,
            "level": "竹",
            "use_mock": True,
            "use_debug": False,
        },
    )
    assert resp.status_code == 200, f"start failed: {resp.text[:200]}"
    return resp.json()


class TestIT1StepFullRun:
    """IT-1: M1→M5 完走テスト。"""

    def test_it1_step_start_returns_task_id_and_m1(self):
        d = _start()
        assert "task_id" in d
        assert len(d["task_id"]) == 8
        assert d["next_stage"] == "m2"
        assert isinstance(d["m1_output"], dict)

    def test_it1_step_next_m2_to_m5_all_done(self):
        d = _start()
        task_id = d["task_id"]

        stages = ["m2", "m3", "m4"]
        for expected_stage in stages:
            r = client.post(f"/api/step/{task_id}/next")
            assert r.status_code == 200, f"{expected_stage} next failed: {r.text[:100]}"
            body = r.json()
            assert body["step"] == expected_stage
            assert body["status"] == "done"
            assert isinstance(body["output"], dict)

        # M5 → all_done
        r = client.post(f"/api/step/{task_id}/next")
        assert r.status_code == 200, f"m5 next failed: {r.text[:100]}"
        body = r.json()
        assert body["step"] == "m5"
        assert body["status"] == "all_done"
        assert body["next_stage"] is None


class TestIT2OutputSchema:
    """IT-2: 各ステージの出力スキーマ検証。"""

    @pytest.fixture(scope="class")
    def task_data(self):
        d = _start()
        task_id = d["task_id"]
        # 全ステージ実行
        for _ in range(4):
            client.post(f"/api/step/{task_id}/next")
        return {"task_id": task_id, "m1_output": d["m1_output"]}

    def test_it2_m1_output_has_sections_count(self, task_data):
        m1 = task_data["m1_output"]
        # serialize_m1 は section_count（複数形なし）を返す
        assert "section_count" in m1
        assert isinstance(m1["section_count"], int)
        assert m1["section_count"] > 0

    def test_it2_m1_output_has_company_name(self, task_data):
        m1 = task_data["m1_output"]
        assert "company_name" in m1

    def test_it2_m2_output_has_applicable_entries(self, task_data):
        r = client.get(f"/api/step/{task_data['task_id']}/output/m2")
        assert r.status_code == 200
        out = r.json()["output"]
        # serialize_m2 は applied_count を返す
        assert "applied_count" in out
        assert isinstance(out["applied_count"], int)
        assert out["applied_count"] > 0

    def test_it2_m2_output_has_warnings_list(self, task_data):
        r = client.get(f"/api/step/{task_data['task_id']}/output/m2")
        out = r.json()["output"]
        assert "warnings" in out
        assert isinstance(out["warnings"], list)

    def test_it2_m3_output_has_total_gaps(self, task_data):
        r = client.get(f"/api/step/{task_data['task_id']}/output/m3")
        out = r.json()["output"]
        assert "total_gaps" in out
        assert isinstance(out["total_gaps"], int)

    def test_it2_m3_output_has_by_change_type(self, task_data):
        r = client.get(f"/api/step/{task_data['task_id']}/output/m3")
        out = r.json()["output"]
        assert "by_change_type" in out
        assert isinstance(out["by_change_type"], dict)

    def test_it2_m4_output_has_proposals_count(self, task_data):
        r = client.get(f"/api/step/{task_data['task_id']}/output/m4")
        out = r.json()["output"]
        assert "proposals_count" in out
        assert isinstance(out["proposals_count"], int)

    def test_it2_m5_output_has_report_markdown(self, task_data):
        r = client.get(f"/api/step/{task_data['task_id']}/output/m5")
        out = r.json()["output"]
        assert "report_markdown" in out
        assert isinstance(out["report_markdown"], str)
        assert len(out["report_markdown"]) > 1000  # レポートは1000文字以上

    def test_it2_m5_output_has_char_count(self, task_data):
        r = client.get(f"/api/step/{task_data['task_id']}/output/m5")
        out = r.json()["output"]
        assert "char_count" in out
        assert isinstance(out["char_count"], int)
        assert out["char_count"] > 1000


class TestIT3GetOutput:
    """IT-3: GET /api/step/{task_id}/output/{stage} 全5ステージ。"""

    @pytest.fixture(scope="class")
    def completed_task_id(self):
        d = _start()
        task_id = d["task_id"]
        for _ in range(4):
            client.post(f"/api/step/{task_id}/next")
        return task_id

    @pytest.mark.parametrize("stage", ["m1", "m2", "m3", "m4", "m5"])
    def test_it3_get_output_all_stages_200(self, completed_task_id, stage):
        r = client.get(f"/api/step/{completed_task_id}/output/{stage}")
        assert r.status_code == 200
        body = r.json()
        assert body["task_id"] == completed_task_id
        assert body["stage"] == stage
        assert isinstance(body["output"], dict)
        assert len(body["output"]) > 0


class TestIT4RunAll:
    """IT-4: start → run-all 残り一括実行。"""

    def test_it4_run_all_from_start_completes(self):
        d = _start()
        task_id = d["task_id"]

        r = client.post(f"/api/step/{task_id}/run-all")
        assert r.status_code == 200, f"run-all failed: {r.text[:200]}"
        body = r.json()
        assert body["status"] == "done"
        assert body["result"] is not None

    def test_it4_run_all_from_middle_completes(self):
        """M1 start → M2 next → run-all で M3〜M5 一括。"""
        d = _start()
        task_id = d["task_id"]

        # M2 まで実行
        r = client.post(f"/api/step/{task_id}/next")
        assert r.status_code == 200

        # run-all (M3, M4, M5)
        r = client.post(f"/api/step/{task_id}/run-all")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "done"


class TestIT5ErrorHandling:
    """IT-5: エラーハンドリング（404/422）。"""

    def test_it5_next_on_unknown_task_404(self):
        r = client.post("/api/step/xxxxxxxx/next")
        assert r.status_code == 404

    def test_it5_output_on_unknown_task_404(self):
        r = client.get("/api/step/xxxxxxxx/output/m1")
        assert r.status_code == 404

    def test_it5_output_invalid_stage_422(self):
        d = _start()
        task_id = d["task_id"]
        r = client.get(f"/api/step/{task_id}/output/m99")
        assert r.status_code == 422

    def test_it5_next_on_completed_task_422(self):
        d = _start()
        task_id = d["task_id"]
        # 全完了
        for _ in range(4):
            client.post(f"/api/step/{task_id}/next")
        # 再度 next → 422
        r = client.post(f"/api/step/{task_id}/next")
        assert r.status_code == 422

    def test_it5_run_all_on_completed_422(self):
        d = _start()
        task_id = d["task_id"]
        client.post(f"/api/step/{task_id}/run-all")
        r = client.post(f"/api/step/{task_id}/run-all")
        assert r.status_code == 422
