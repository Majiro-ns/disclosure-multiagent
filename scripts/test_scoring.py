"""
test_scoring.py
===============
disclosure-multiagent T012: 開示変更スコアリング API のテスト

テスト対象エンドポイント:
  TC-SC1: POST /api/scoring/document    → 200, score_id (UUID4), risk_level返却
  TC-SC2: POST /api/scoring/document    → 空テキスト → 400
  TC-SC3: GET  /api/scoring/history     → 空DB → count=0
  TC-SC4: GET  /api/scoring/history     → スコアリング後 → count=1
  TC-SC5: POST /api/scoring/document    → 変更語彙含むテキスト → change_intensity_score > 0
  TC-SC6: compute_change_intensity 純粋関数テスト → 手計算検証
  TC-SC7: compute_scores 純粋関数テスト → weighted average 検証
  TC-SC8: compute_risk_level 純粋関数テスト → 境界値検証

CHECK-9 根拠:
  TC-SC1: UUID4形式・scored_at・overall_risk_score (0-100) を検証。
          risk_level ∈ {"low", "medium", "high"} を確認。
  TC-SC2: 空テキスト "" → HTTPException(400)。
  TC-SC3: score_history テーブルが空 → count=0。
  TC-SC4: score_document 後 → count=1。
  TC-SC5: "変更・改正・廃止・新設" 含む → matched=4件 → score=4/8*200=100.0 (cap)
  TC-SC6: vocab=["変更","改正","廃止"] (3件), text="今回の変更と廃止" → matched=2
          score = min(2/3*200, 100.0) = min(133.3, 100.0) = 100.0
          vocab=["変更","改正","廃止"], text="特になし" → matched=0 → score=0.0
  TC-SC7: coverage_rate=0.4, change_intensity=50.0
          checklist_coverage_score=40.0
          overall_risk_score=round(0.6*40.0+0.4*50.0, 1)=round(24+20, 1)=44.0 → "medium"
  TC-SC8: score=39.9 → "low", score=40.0 → "medium", score=70.0 → "high"

作成: 足軽6 cmd_285k_disclosure_T012
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("USE_MOCK_LLM", "true")

_SCRIPTS_DIR = Path(__file__).parent
_PROJECT_ROOT = _SCRIPTS_DIR.parent
for p in [str(_SCRIPTS_DIR), str(_PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)


def _make_client(db_path: str):
    """一時 DB を指定して TestClient を生成する。"""
    os.environ["DISCLOSURE_DB_PATH"] = db_path
    from importlib import reload
    import api.services.checklist_eval_service as svc_eval
    reload(svc_eval)
    import api.services.scoring_service as svc_score
    reload(svc_score)
    import api.routers.checklist_eval as eval_mod
    reload(eval_mod)
    import api.routers.checklist_stats as stats_mod
    reload(stats_mod)
    import api.routers.scoring as score_mod
    reload(score_mod)
    import api.main as main_mod
    reload(main_mod)
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app, raise_server_exceptions=False)


# ──────────────────────────────────────────────────────────────────────────────
# TC-SC1 / TC-SC2: POST /api/scoring/document
# ──────────────────────────────────────────────────────────────────────────────

class TestScoreDocument(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = str(Path(self._tmpdir.name) / "test.db")
        self.client = _make_client(db_path)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_tc_sc1_score_document_returns_score_id_and_risk_level(self):
        """TC-SC1: 正常テキスト → 200, score_id (UUID4), risk_level返却。

        根拠: score_document が UUID4 生成 + 3スコア + risk_level を返す。
             risk_level ∈ {"low","medium","high"} であることを確認。
        """
        resp = self.client.post(
            "/api/scoring/document",
            json={"disclosure_text": "当期において固定資産の減損損失を計上しました。"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()

        import re
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        self.assertRegex(body["score_id"], uuid_pattern, "score_id が UUID4 形式でない")

        self.assertIn("scored_at", body)
        self.assertIn("overall_risk_score", body)
        self.assertIn("checklist_coverage_score", body)
        self.assertIn("change_intensity_score", body)
        self.assertIn("risk_level", body)
        self.assertIn(body["risk_level"], {"low", "medium", "high"})
        self.assertIn("top_matched_items", body)

        # スコアの範囲チェック
        for key in ["overall_risk_score", "checklist_coverage_score", "change_intensity_score"]:
            self.assertGreaterEqual(body[key], 0.0)
            self.assertLessEqual(body[key], 100.0)

    def test_tc_sc2_score_document_empty_text_returns_400(self):
        """TC-SC2: 空テキスト → 400 Bad Request。

        根拠: scoring_service.score_document は空テキストで ValueError → router が 400 に変換。
        """
        resp = self.client.post(
            "/api/scoring/document",
            json={"disclosure_text": ""},
        )
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_tc_sc5_change_vocabulary_text_raises_intensity_score(self):
        """TC-SC5: 変更語彙4語含むテキスト → change_intensity_score > 0。

        根拠: "変更・改正・廃止・新設" が CHANGE_VOCABULARY 中4語にマッチ
             → score = min(4/8*200, 100.0) = 100.0 > 0。
        """
        resp = self.client.post(
            "/api/scoring/document",
            json={"disclosure_text": "今期の変更点として改正・廃止・新設がありました。"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertGreater(body["change_intensity_score"], 0.0,
                           "変更語彙含む文章で intensity_score>0 であること")


# ──────────────────────────────────────────────────────────────────────────────
# TC-SC3 / TC-SC4: GET /api/scoring/history
# ──────────────────────────────────────────────────────────────────────────────

class TestScoringHistory(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = str(Path(self._tmpdir.name) / "test.db")
        self.client = _make_client(db_path)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_tc_sc3_history_empty_db(self):
        """TC-SC3: 空DB → count=0, history=[]。

        根拠: score_history テーブルが空 → get_score_history([]) → 空リスト。
        """
        resp = self.client.get("/api/scoring/history")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["history"], [])

    def test_tc_sc4_history_after_score(self):
        """TC-SC4: score_document 後 → history count=1, 期待フィールドを含む。

        根拠: score_document が score_history テーブルに INSERT
             → GET /history が count=1, 各フィールドを返す。
        """
        self.client.post(
            "/api/scoring/document",
            json={"disclosure_text": "退職給付費用の変更について注記します。"},
        )

        resp = self.client.get("/api/scoring/history")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(len(body["history"]), 1)

        item = body["history"][0]
        for field in ["score_id", "scored_at", "text_snippet",
                      "overall_risk_score", "risk_level", "top_matched_items"]:
            self.assertIn(field, item, f"history[0] に {field} が欠落")


# ──────────────────────────────────────────────────────────────────────────────
# TC-SC6 / TC-SC7 / TC-SC8: 純粋関数テスト
# ──────────────────────────────────────────────────────────────────────────────

class TestPureFunctions(unittest.TestCase):

    def test_tc_sc6_compute_change_intensity_exact_values(self):
        """TC-SC6: compute_change_intensity の手計算検証。

        根拠:
          vocab=["変更","改正","廃止"] (3件), text="今回の変更と廃止"
            → matched=2, score=min(2/3*200, 100.0)=min(133.3..,100.0)=100.0

          vocab=["変更","改正","廃止"], text="特になし"
            → matched=0, score=0.0
        """
        from api.services.scoring_service import compute_change_intensity
        vocab3 = ["変更", "改正", "廃止"]

        score_high = compute_change_intensity("今回の変更と廃止について", vocab3)
        self.assertAlmostEqual(score_high, 100.0, places=1,
                               msg="2/3*200=133.3 → cap 100.0")

        score_zero = compute_change_intensity("特になし", vocab3)
        self.assertAlmostEqual(score_zero, 0.0, places=1,
                               msg="マッチなし → 0.0")

    def test_tc_sc6b_compute_change_intensity_partial(self):
        """TC-SC6（補足）: 部分マッチの場合の計算検証。

        根拠:
          vocab=["変更","改正","廃止","新設"] (4件), text="今期の変更のみ"
            → matched=1, score=round(min(1/4*200, 100.0), 1)=round(50.0, 1)=50.0
        """
        from api.services.scoring_service import compute_change_intensity
        vocab4 = ["変更", "改正", "廃止", "新設"]
        score = compute_change_intensity("今期の変更のみ", vocab4)
        self.assertAlmostEqual(score, 50.0, places=1)

    def test_tc_sc7_compute_scores_weighted_average(self):
        """TC-SC7: compute_scores の weighted average 手計算検証。

        根拠:
          coverage_rate=0.4, change_intensity=50.0
          checklist_coverage_score = round(0.4*100, 1) = 40.0
          overall_risk_score = round(0.6*40.0 + 0.4*50.0, 1) = round(44.0, 1) = 44.0
          44.0 ∈ [40, 70) → risk_level = "medium"
        """
        from api.services.scoring_service import compute_scores
        result = compute_scores(coverage_rate=0.4, change_intensity_score=50.0)

        self.assertAlmostEqual(result["checklist_coverage_score"], 40.0, places=1)
        self.assertAlmostEqual(result["overall_risk_score"], 44.0, places=1)
        self.assertEqual(result["risk_level"], "medium")

    def test_tc_sc8_compute_risk_level_boundaries(self):
        """TC-SC8: compute_risk_level 境界値検証。

        根拠:
          score=39.9 → < 40 → "low"
          score=40.0 → >= 40 → "medium"
          score=69.9 → < 70 → "medium"
          score=70.0 → >= 70 → "high"
        """
        from api.services.scoring_service import compute_risk_level

        self.assertEqual(compute_risk_level(39.9), "low")
        self.assertEqual(compute_risk_level(40.0), "medium")
        self.assertEqual(compute_risk_level(69.9), "medium")
        self.assertEqual(compute_risk_level(70.0), "high")


# ──────────────────────────────────────────────────────────────────────────────
# TC-TS1〜TC-TS8: 松竹梅ティアスコア テスト (C06 cmd_374k_a7)
# ──────────────────────────────────────────────────────────────────────────────

class TestComputeTierScore(unittest.TestCase):
    """TC-TS1/TC-TS2: compute_tier_score 純粋関数テスト。"""

    def setUp(self):
        from api.services.scoring_service import compute_tier_score
        self._func = compute_tier_score

    def test_tc_ts1_basic_calculation(self):
        """TC-TS1: 10必須中4ギャップ → covered=6 → score=60 → 梅ライン境界。

        根拠: required_count=10, gaps_found=4 → covered=6
              round(6/10*100) = 60
        """
        law_entries = [{"tier_requirement": "必須"}] * 10
        gap_results = [{"has_gap": True}] * 4 + [{"has_gap": False}] * 6
        score = self._func(gap_results, law_entries)
        self.assertEqual(score, 60)

    def test_tc_ts1b_all_covered(self):
        """TC-TS1b: 10必須中ギャップなし → score=100。

        根拠: covered=10, round(10/10*100)=100
        """
        law_entries = [{"tier_requirement": "必須"}] * 10
        gap_results = [{"has_gap": False}] * 10
        self.assertEqual(self._func(gap_results, law_entries), 100)

    def test_tc_ts1c_all_gaps(self):
        """TC-TS1c: 10必須全てギャップ → score=0。

        根拠: covered=max(0, 10-10)=0, round(0/10*100)=0
        """
        law_entries = [{"tier_requirement": "必須"}] * 10
        gap_results = [{"has_gap": True}] * 10
        self.assertEqual(self._func(gap_results, law_entries), 0)

    def test_tc_ts2_empty_law_entries(self):
        """TC-TS2: law_entries が空 → 0。

        根拠: required_count=0 → early return 0
        """
        self.assertEqual(self._func([], []), 0)

    def test_tc_ts2b_no_required_entries(self):
        """TC-TS2b: law_entries に "必須" なし → 0。

        根拠: required_count=0（全て "推奨"）→ early return 0
        """
        law_entries = [{"tier_requirement": "推奨"}] * 5
        gap_results = [{"has_gap": True}] * 3
        self.assertEqual(self._func(gap_results, law_entries), 0)

    def test_tc_ts2c_has_gap_none_treated_as_covered(self):
        """TC-TS2c: has_gap=None は「カバー済み」扱い（True のみカウント）。

        根拠: has_gap is True のみ gaps_found に加算
              10必須, gaps_found=0 (Noneは除外) → covered=10 → score=100
        """
        law_entries = [{"tier_requirement": "必須"}] * 10
        gap_results = [{"has_gap": None}] * 10
        self.assertEqual(self._func(gap_results, law_entries), 100)

    def test_tc_ts2d_score_caps_at_100(self):
        """TC-TS2d: gap_results が law_entries より少なくてもスコアは100以下。

        根拠: covered = max(0, required - gaps_found), min(100, ...)
              10必須, gaps_found=0 (gap_results空) → 100
        """
        law_entries = [{"tier_requirement": "必須"}] * 10
        self.assertEqual(self._func([], law_entries), 100)

    def test_tc_ts1d_only_required_counted(self):
        """TC-TS1d: 推奨エントリはスコア計算に含まれない。

        根拠: required_count = 必須のみ = 5
              gaps_found=2, covered=3, round(3/5*100)=60
        """
        law_entries = (
            [{"tier_requirement": "必須"}] * 5
            + [{"tier_requirement": "推奨"}] * 5
        )
        gap_results = [{"has_gap": True}] * 2 + [{"has_gap": False}] * 8
        score = self._func(gap_results, law_entries)
        self.assertEqual(score, 60)


class TestGetTierLabel(unittest.TestCase):
    """TC-TS3: get_tier_label 境界値テスト。"""

    def setUp(self):
        from api.services.scoring_service import get_tier_label
        self._func = get_tier_label

    def test_tc_ts3_boundary_59_未達(self):
        """TC-TS3a: score=59 → "未達"（梅ライン60未満）。"""
        self.assertEqual(self._func(59), "未達")

    def test_tc_ts3_boundary_60_梅(self):
        """TC-TS3b: score=60 → "梅"（梅ライン到達）。"""
        self.assertEqual(self._func(60), "梅")

    def test_tc_ts3_boundary_79_梅(self):
        """TC-TS3c: score=79 → "梅"（竹ライン80未満）。"""
        self.assertEqual(self._func(79), "梅")

    def test_tc_ts3_boundary_80_竹(self):
        """TC-TS3d: score=80 → "竹"（竹ライン到達）。"""
        self.assertEqual(self._func(80), "竹")

    def test_tc_ts3_boundary_94_竹(self):
        """TC-TS3e: score=94 → "竹"（松ライン95未満）。"""
        self.assertEqual(self._func(94), "竹")

    def test_tc_ts3_boundary_95_松(self):
        """TC-TS3f: score=95 → "松"（松ライン到達）。"""
        self.assertEqual(self._func(95), "松")

    def test_tc_ts3_boundary_100_松(self):
        """TC-TS3g: score=100 → "松"（最大値）。"""
        self.assertEqual(self._func(100), "松")

    def test_tc_ts3_boundary_0_未達(self):
        """TC-TS3h: score=0 → "未達"（最小値）。"""
        self.assertEqual(self._func(0), "未達")


class TestGetUpgradeItems(unittest.TestCase):
    """TC-TS4: get_upgrade_items テスト。"""

    def setUp(self):
        from api.services.scoring_service import get_upgrade_items
        self._func = get_upgrade_items

    def test_tc_ts4_score50_target_梅_returns_items(self):
        """TC-TS4a: score=50 (未達), target="梅" → 梅到達用アイテムを返す。"""
        items = self._func(50, "梅")
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)

    def test_tc_ts4_score62_target_竹_returns_items(self):
        """TC-TS4b: score=62 (梅), target="竹" → 竹到達用アイテムを返す。

        根拠: タスク例「upgrade_items: ['有価証券報告書への人的資本KPI追記', 'SSBJ早期適用宣言']」
        """
        items = self._func(62, "竹")
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)
        # 竹到達アイテムに「SSBJ」が含まれることを確認
        joined = " ".join(items)
        self.assertIn("SSBJ", joined, "竹到達アイテムに SSBJ 関連項目が含まれること")

    def test_tc_ts4_score82_target_松_returns_items(self):
        """TC-TS4c: score=82 (竹), target="松" → 松到達用アイテムを返す。"""
        items = self._func(82, "松")
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)

    def test_tc_ts4_already_at_target_returns_empty(self):
        """TC-TS4d: score=95 (松), target="松" → 既に達成 → 空リスト。

        根拠: current_label="松" >= target_order["松"] → []
        """
        items = self._func(95, "松")
        self.assertEqual(items, [])

    def test_tc_ts4_already_above_target_returns_empty(self):
        """TC-TS4e: score=85 (竹), target="梅" → 目標以上 → 空リスト。"""
        items = self._func(85, "梅")
        self.assertEqual(items, [])

    def test_tc_ts4_invalid_target_raises_value_error(self):
        """TC-TS4f: target_tier が無効 → ValueError。

        根拠: ValueError("target_tier は '梅'/'竹'/'松'...")
        """
        with self.assertRaises(ValueError):
            self._func(50, "invalid")


class TestTierScoreEndpoint(unittest.TestCase):
    """TC-TS5/TC-TS6: POST /api/scoring/tier エンドポイントテスト。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = str(Path(self._tmpdir.name) / "test.db")
        self.client = _make_client(db_path)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_tc_ts5_tier_endpoint_returns_valid_response(self):
        """TC-TS5: 正常テキスト → 200, tier_score (0-100), tier_label ∈ 有効値。

        根拠: evaluate_and_save が coverage_rate を返し
              tier_score = round(coverage_rate * 100) が 0-100 の整数。
              tier_label ∈ {"未達","梅","竹","松"}。
        """
        resp = self.client.post(
            "/api/scoring/tier",
            json={"disclosure_text": "当期において固定資産の減損損失を計上しました。"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()

        self.assertIn("tier_score", body)
        self.assertIn("tier_label", body)
        self.assertIn("upgrade_items", body)

        self.assertIsInstance(body["tier_score"], int)
        self.assertGreaterEqual(body["tier_score"], 0)
        self.assertLessEqual(body["tier_score"], 100)

        self.assertIn(body["tier_label"], {"未達", "梅", "竹", "松"},
                      f"tier_label '{body['tier_label']}' が有効値でない")

        self.assertIsInstance(body["upgrade_items"], list)

    def test_tc_ts6_tier_endpoint_empty_text_returns_400(self):
        """TC-TS6: 空テキスト → 400 Bad Request。

        根拠: ルーターが空テキストを HTTPException(400) に変換。
        """
        resp = self.client.post(
            "/api/scoring/tier",
            json={"disclosure_text": ""},
        )
        self.assertEqual(resp.status_code, 400, resp.text)

    def test_tc_ts7_tier_endpoint_with_target_tier(self):
        """TC-TS7: target_tier 指定時、upgrade_items が対応するアイテムを返す。

        根拠: target_tier="竹" を指定 → get_upgrade_items(score, "竹") の結果が返る。
        """
        resp = self.client.post(
            "/api/scoring/tier",
            json={
                "disclosure_text": "人材育成および従業員エンゲージメントの向上に注力しています。",
                "target_tier": "竹",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        # tier_label が 竹以上なら upgrade_items は空、未満なら非空
        if body["tier_label"] in ("未達", "梅"):
            self.assertGreater(len(body["upgrade_items"]), 0,
                               "tier_label<竹 の場合 upgrade_items が空でないこと")

    def test_tc_ts8_tier_label_consistency(self):
        """TC-TS8: tier_score と tier_label の整合性検証。

        根拠: get_tier_label の境界値（60/80/95）と tier_score の整合性。
        """
        from api.services.scoring_service import get_tier_label
        resp = self.client.post(
            "/api/scoring/tier",
            json={"disclosure_text": "減損損失、退職給付、有価証券報告書、人的資本"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()

        expected_label = get_tier_label(body["tier_score"])
        self.assertEqual(body["tier_label"], expected_label,
                         f"tier_score={body['tier_score']} に対する tier_label が不整合")


if __name__ == "__main__":
    unittest.main()
