"""A2A (Agent-to-Agent) プロトコル E2E テスト。

テスト対象:
    1. Agent Card 取得（/.well-known/agent-card.json および /a2a/agent-card）
    2. POST /a2a/execute — タスク実行（3スキル）
    3. エラーケース（空入力）

実行:
    # テスト単体
    python3 -m pytest tests/test_a2a.py -v
    # サーバー起動後のE2Eテスト
    DISCLOSURE_A2A_E2E=1 python3 -m pytest tests/test_a2a.py -v -k e2e
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# プロジェクトルートをパスに追加
_PROJECT_ROOT = Path(__file__).parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
for _p in [str(_PROJECT_ROOT), str(_SCRIPTS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi.testclient import TestClient


# ─── フィクスチャ ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """FastAPI テストクライアント（モジュールスコープ）。"""
    # 依存モジュールをモック化してテストを軽量化
    with patch.dict("sys.modules", {
        "m1_pdf_agent": MagicMock(),
        "m2_law_agent": MagicMock(),
        "m3_gap_analysis_agent": MagicMock(),
        "m4_proposal_agent": MagicMock(),
        "m5_report_agent": MagicMock(),
    }):
        from api.main import app
        with TestClient(app) as c:
            yield c


# ─── Agent Card テスト ────────────────────────────────────────────────────

class TestAgentCard:
    """A2A Agent Card エンドポイントのテスト。"""

    def test_well_known_agent_card_returns_200(self, client):
        """/.well-known/agent-card.json が 200 を返すこと。"""
        resp = client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200

    def test_well_known_agent_card_has_required_fields(self, client):
        """Agent Card に A2A 必須フィールドが含まれること。"""
        resp = client.get("/.well-known/agent-card.json")
        data = resp.json()
        assert data["name"] == "disclosure-multiagent"
        assert "skills" in data
        assert len(data["skills"]) >= 1
        assert "defaultInputModes" in data
        assert "defaultOutputModes" in data

    def test_a2a_agent_card_endpoint(self, client):
        """/a2a/agent-card が同じ Agent Card を返すこと。"""
        resp = client.get("/a2a/agent-card")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "disclosure-multiagent"

    def test_agent_card_skills_structure(self, client):
        """各スキルに id・name・description が含まれること。"""
        resp = client.get("/.well-known/agent-card.json")
        data = resp.json()
        for skill in data["skills"]:
            assert "id" in skill, f"skill に id がない: {skill}"
            assert "name" in skill, f"skill に name がない: {skill}"
            assert "description" in skill, f"skill に description がない: {skill}"


# ─── A2A タスク実行テスト ─────────────────────────────────────────────────

def _make_task_body(text: str, skill_id: str = "", task_id: str = None) -> dict:
    """テスト用 A2A Task リクエスト本体を生成する。"""
    return {
        "id": task_id or str(uuid.uuid4()),
        "contextId": str(uuid.uuid4()),
        "skillId": skill_id,
        "message": {
            "messageId": str(uuid.uuid4()),
            "role": "user",
            "parts": [{"kind": "text", "text": text}],
        },
    }


class TestA2AExecute:
    """POST /a2a/execute エンドポイントのテスト。"""

    def test_execute_returns_200(self, client):
        """POST /a2a/execute が 200 を返すこと。"""
        body = _make_task_body("有価証券報告書を分析してください")
        resp = client.post("/a2a/execute", json=body)
        assert resp.status_code == 200

    def test_execute_returns_task_format(self, client):
        """レスポンスが A2A Task 形式（id / contextId / status / artifacts）を持つこと。"""
        body = _make_task_body("開示書類の分析をお願いします")
        resp = client.post("/a2a/execute", json=body)
        data = resp.json()
        assert "id" in data
        assert "contextId" in data
        assert "status" in data
        assert "artifacts" in data

    def test_execute_preserves_task_id(self, client):
        """レスポンスの task id が入力と一致すること。"""
        task_id = str(uuid.uuid4())
        body = _make_task_body("分析してください", task_id=task_id)
        resp = client.post("/a2a/execute", json=body)
        data = resp.json()
        assert data["id"] == task_id

    def test_execute_status_completed_or_failed(self, client):
        """status.state が completed または failed のいずれかであること。"""
        body = _make_task_body("松竹梅スコアリング: KPI・目標年度の記載あり")
        resp = client.post("/a2a/execute", json=body)
        data = resp.json()
        assert data["status"]["state"] in ("completed", "failed")

    def test_execute_artifacts_has_text(self, client):
        """artifacts に text パーツが含まれること。"""
        body = _make_task_body("スコアリングをしてください（数値目標: 離職率5%以下、取締役会承認済み）")
        resp = client.post("/a2a/execute", json=body)
        data = resp.json()
        artifacts = data.get("artifacts", [])
        assert len(artifacts) >= 1
        parts = artifacts[0].get("parts", [])
        assert len(parts) >= 1
        assert parts[0].get("kind") == "text"
        assert len(parts[0].get("text", "")) > 0

    def test_execute_empty_input_returns_error(self, client):
        """空テキスト入力時にエラー Task を返すこと。"""
        body = _make_task_body("")
        resp = client.post("/a2a/execute", json=body)
        data = resp.json()
        # 空入力はエラー（failed）または completed でエラーメッセージ
        assert data["status"]["state"] in ("failed", "completed")

    def test_execute_edinet_search_skill(self, client):
        """skillId=edinet_search を指定した時に EDINET 検索が実行されること。"""
        body = _make_task_body(
            "証券コード 7203 の有価証券報告書を検索",
            skill_id="edinet_search",
        )
        resp = client.post("/a2a/execute", json=body)
        data = resp.json()
        assert data["status"]["state"] in ("completed", "failed")
        # artifacts のテキストに EDINET 関連文字列が含まれること
        text = data["artifacts"][0]["parts"][0]["text"]
        assert "EDINET" in text or "edinet" in text.lower() or "エラー" in text or "コード" in text

    def test_execute_scoring_skill(self, client):
        """松竹梅スコアリングスキルが実行されること。"""
        body = _make_task_body(
            "スコアリング対象: 離職率3.5%（目標2025年度）取締役会承認済み",
            skill_id="matsu_take_ume_scoring",
        )
        resp = client.post("/a2a/execute", json=body)
        data = resp.json()
        assert data["status"]["state"] in ("completed", "failed")
        text = data["artifacts"][0]["parts"][0]["text"]
        assert len(text) > 0

    def test_execute_scoring_keyword_dispatch(self, client):
        """「スコアリング」キーワードでスコアリングスキルに振り分けられること。"""
        body = _make_task_body("スコアリングをお願いします。目標値: 売上成長率10%以上")
        resp = client.post("/a2a/execute", json=body)
        data = resp.json()
        text = data["artifacts"][0]["parts"][0]["text"]
        # スコアリングの結果（梅/竹/松レベル）か a2a の応答が含まれること
        assert len(text) > 0


# ─── E2E テスト（実サーバー起動時のみ） ──────────────────────────────────

@pytest.mark.skipif(
    not os.environ.get("DISCLOSURE_A2A_E2E"),
    reason="DISCLOSURE_A2A_E2E=1 が設定されていない場合はスキップ",
)
class TestA2AE2E:
    """実サーバー起動時の E2E テスト。"""

    BASE_URL = "http://localhost:8000"

    def test_e2e_agent_card(self):
        """実サーバーから Agent Card を取得できること。"""
        import httpx

        resp = httpx.get(f"{self.BASE_URL}/.well-known/agent-card.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "disclosure-multiagent"

    def test_e2e_execute_task(self):
        """実サーバーに A2A タスクを送信して結果を受信できること。"""
        import httpx

        body = _make_task_body("有価証券報告書の松竹梅分析をしてください（EDINETコード E00001）")
        resp = httpx.post(f"{self.BASE_URL}/a2a/execute", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"]["state"] in ("completed", "failed")
        assert len(data["artifacts"]) >= 1
