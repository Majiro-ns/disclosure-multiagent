"""
test_api_endpoints.py
=====================
disclosure-multiagent APIエンドポイント基本テスト (cmd_350k_a7a / cmd_350k_a7c)

テスト対象:
  TC-E1: GET  /api/health                          → 200, status=ok
  TC-E2: POST /api/analyze (mock)                  → 200, task_id返却
  TC-E3: GET  /api/checklist                       → 200, itemsリスト
  TC-E4: GET  /api/edinet/search?name=テスト       → 200, resultsリスト
  TC-E5: GET  /api/edinet/search (パラメータなし)  → 400 エラーケース
  TC-E6: POST /api/scoring/document (有効テキスト) → 200, score_id返却
  TC-E7: POST /api/scoring/document (空テキスト)   → 400 エラーケース
  TC-E8: GET  /api/status/{task_id} (有効ID)       → 200, task_id一致
  TC-E9: GET  /api/status/{task_id} (無効ID)       → 404 エラーケース
  TC-E10: GET /api/checklist?required_only=true    → 200, 必須項目のみ
  TC-E11: POST /api/checklist/validate             → 200, coverage_rate返却
  TC-E12: GET /api/edinet/search?sec_code=7203     → 200, sec_codeで検索
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("USE_MOCK_LLM", "true")

_SCRIPTS_DIR = Path(__file__).parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
for _p in [str(_SCRIPTS_DIR), str(_PROJECT_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint(unittest.TestCase):
    """TC-E1: GET /api/health"""

    def test_health_returns_200(self):
        res = client.get("/api/health")
        self.assertEqual(res.status_code, 200)

    def test_health_returns_ok_status(self):
        res = client.get("/api/health")
        body = res.json()
        self.assertEqual(body.get("status"), "ok")
        self.assertEqual(body.get("service"), "disclosure-multiagent")


class TestAnalyzeEndpoint(unittest.TestCase):
    """TC-E2: POST /api/analyze (mock)"""

    def test_analyze_returns_200(self):
        payload = {"use_mock": True, "company_name": "テスト株式会社"}
        res = client.post("/api/analyze", json=payload)
        self.assertEqual(res.status_code, 200)

    def test_analyze_returns_task_id(self):
        payload = {"use_mock": True, "company_name": "テスト株式会社"}
        res = client.post("/api/analyze", json=payload)
        body = res.json()
        self.assertIn("task_id", body)
        self.assertIsInstance(body["task_id"], str)
        self.assertTrue(len(body["task_id"]) > 0)

    def test_analyze_returns_queued_status(self):
        payload = {"use_mock": True}
        res = client.post("/api/analyze", json=payload)
        body = res.json()
        self.assertEqual(body.get("status"), "queued")


class TestChecklistEndpoint(unittest.TestCase):
    """TC-E3: GET /api/checklist"""

    def test_checklist_returns_200(self):
        res = client.get("/api/checklist")
        self.assertEqual(res.status_code, 200)

    def test_checklist_has_required_fields(self):
        res = client.get("/api/checklist")
        body = res.json()
        self.assertIn("version", body)
        self.assertIn("total", body)
        self.assertIn("items", body)

    def test_checklist_items_is_list(self):
        res = client.get("/api/checklist")
        body = res.json()
        self.assertIsInstance(body["items"], list)

    def test_checklist_total_matches_items_length(self):
        res = client.get("/api/checklist")
        body = res.json()
        self.assertEqual(body["total"], len(body["items"]))


class TestEdinetSearchEndpoint(unittest.TestCase):
    """TC-E4/TC-E5: GET /api/edinet/search"""

    def test_search_with_name_returns_200(self):
        res = client.get("/api/edinet/search", params={"name": "テスト"})
        self.assertEqual(res.status_code, 200)

    def test_search_with_name_has_results_field(self):
        res = client.get("/api/edinet/search", params={"name": "テスト"})
        body = res.json()
        self.assertIn("results", body)
        self.assertIn("total", body)
        self.assertIsInstance(body["results"], list)

    def test_search_without_params_returns_400(self):
        """TC-E5: エラーケース - パラメータなしは400"""
        res = client.get("/api/edinet/search")
        self.assertEqual(res.status_code, 400)


class TestScoringEndpoint(unittest.TestCase):
    """TC-E6/TC-E7: POST /api/scoring/document"""

    def test_scoring_with_valid_text_returns_200(self):
        payload = {
            "disclosure_text": "当社は固定資産の減価償却を定額法で行っております。"
                                "重要な会計方針の変更はございません。"
        }
        res = client.post("/api/scoring/document", json=payload)
        self.assertEqual(res.status_code, 200)

    def test_scoring_returns_score_id(self):
        payload = {
            "disclosure_text": "有価証券報告書における重要な開示変更事項はありません。"
        }
        res = client.post("/api/scoring/document", json=payload)
        body = res.json()
        self.assertIn("score_id", body)
        self.assertIsInstance(body["score_id"], str)

    def test_scoring_returns_risk_fields(self):
        payload = {
            "disclosure_text": "当社の事業リスクとして為替変動リスクがあります。"
        }
        res = client.post("/api/scoring/document", json=payload)
        body = res.json()
        self.assertIn("overall_risk_score", body)
        self.assertIn("risk_level", body)

    def test_scoring_with_empty_text_returns_400(self):
        """TC-E7: エラーケース - 空テキストは400"""
        payload = {"disclosure_text": ""}
        res = client.post("/api/scoring/document", json=payload)
        self.assertEqual(res.status_code, 400)

    def test_scoring_with_whitespace_text_returns_400(self):
        """TC-E7変形: 空白のみも400"""
        payload = {"disclosure_text": "   "}
        res = client.post("/api/scoring/document", json=payload)
        self.assertEqual(res.status_code, 400)


class TestStatusEndpoint(unittest.TestCase):
    """TC-E8/TC-E9: GET /api/status/{task_id}"""

    def test_status_returns_200_for_valid_task(self):
        """TC-E8: POST /api/analyze で作成したタスクの status を取得"""
        # まず analyze でタスクを作成
        payload = {"use_mock": True}
        analyze_res = client.post("/api/analyze", json=payload)
        self.assertEqual(analyze_res.status_code, 200)
        task_id = analyze_res.json()["task_id"]

        # status エンドポイントで確認
        res = client.get(f"/api/status/{task_id}")
        self.assertEqual(res.status_code, 200)

    def test_status_returns_task_id_in_body(self):
        """TC-E8: status レスポンスに task_id が含まれる"""
        payload = {"use_mock": True}
        analyze_res = client.post("/api/analyze", json=payload)
        task_id = analyze_res.json()["task_id"]

        res = client.get(f"/api/status/{task_id}")
        body = res.json()
        self.assertEqual(body.get("task_id"), task_id)

    def test_status_returns_404_for_unknown_task(self):
        """TC-E9: エラーケース - 存在しないタスクIDは404"""
        res = client.get("/api/status/nonexistent-task-id")
        self.assertEqual(res.status_code, 404)


class TestChecklistRequiredOnly(unittest.TestCase):
    """TC-E10: GET /api/checklist?required_only=true"""

    def test_checklist_required_only_returns_200(self):
        """TC-E10: required_only=true クエリパラメータ付きで200"""
        res = client.get("/api/checklist", params={"required_only": "true"})
        self.assertEqual(res.status_code, 200)

    def test_checklist_required_only_items_are_subset(self):
        """TC-E10: required_only の件数は全件数以下"""
        all_res = client.get("/api/checklist")
        req_res = client.get("/api/checklist", params={"required_only": "true"})
        all_total = all_res.json()["total"]
        req_total = req_res.json()["total"]
        self.assertLessEqual(req_total, all_total)


class TestChecklistValidate(unittest.TestCase):
    """TC-E11: POST /api/checklist/validate"""

    def test_validate_returns_200(self):
        """TC-E11: テキスト照合で200を返す"""
        payload = {"disclosure_text": "当社は役員報酬について有価証券報告書に開示しております。"}
        res = client.post("/api/checklist/validate", json=payload)
        self.assertEqual(res.status_code, 200)

    def test_validate_returns_coverage_rate(self):
        """TC-E11: レスポンスに coverage_rate が含まれる"""
        payload = {"disclosure_text": "固定資産の減価償却は定額法を採用しています。"}
        res = client.post("/api/checklist/validate", json=payload)
        body = res.json()
        self.assertIn("coverage_rate", body)
        self.assertIn("matched_count", body)
        self.assertIn("total_checked", body)


class TestEdinetSearchBySecCode(unittest.TestCase):
    """TC-E12: GET /api/edinet/search?sec_code=XXXX"""

    def test_search_by_sec_code_returns_200(self):
        """TC-E12: sec_code パラメータで検索して200を返す"""
        res = client.get("/api/edinet/search", params={"sec_code": "7203"})
        self.assertEqual(res.status_code, 200)

    def test_search_by_sec_code_has_results_field(self):
        """TC-E12: sec_code 検索のレスポンスに results と total が含まれる"""
        res = client.get("/api/edinet/search", params={"sec_code": "7203"})
        body = res.json()
        self.assertIn("results", body)
        self.assertIn("total", body)


if __name__ == "__main__":
    unittest.main()
