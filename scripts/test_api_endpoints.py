"""
test_api_endpoints.py
=====================
disclosure-multiagent APIエンドポイント基本テスト (cmd_350k_a7a)

テスト対象:
  TC-E1: GET  /api/health                          → 200, status=ok
  TC-E2: POST /api/analyze (mock)                  → 200, task_id返却
  TC-E3: GET  /api/checklist                       → 200, itemsリスト
  TC-E4: GET  /api/edinet/search?name=テスト       → 200, resultsリスト
  TC-E5: GET  /api/edinet/search (パラメータなし)  → 400 エラーケース
  TC-E6: POST /api/scoring/document (有効テキスト) → 200, score_id返却
  TC-E7: POST /api/scoring/document (空テキスト)   → 400 エラーケース
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


if __name__ == "__main__":
    unittest.main()
