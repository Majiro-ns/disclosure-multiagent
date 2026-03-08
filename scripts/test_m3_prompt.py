"""test_m3_prompt.py
===================
dis_b03_a6: M3ギャップ判定プロンプト改善テスト

テスト仕様:
  TP-1: SYSTEM_PROMPT に has_gap 判定基準の説明が含まれること
  TP-2: SYSTEM_PROMPT に confidence 高/中/低 の定義が含まれること
  TP-3: SYSTEM_PROMPT に JSON フォーマット例が含まれること
  TP-4: _build_user_prompt() が「【ギャップ判定タスク】」で始まること
  TP-5: _build_user_prompt() に開示項目・法令根拠・変更種別が含まれること
  TP-6: _build_user_prompt() にテーブルデータの注記が含まれること（テーブルあり時）
  TP-7: _build_user_prompt() にテーブルなしの場合はテーブルセクションが含まれないこと
  TP-8: _mock_judge_response() が数値系項目でテキスト内数値+キーワードがあれば充足判定
  TP-9: _mock_judge_response() が数値系項目でキーワードなしの場合ギャップ判定
  TP-10: _mock_judge_response() が定性系項目でキーワードありの場合充足判定（confidence: medium）
  TP-11: _mock_judge_response() が定性系項目でキーワードなしの場合ギャップ判定（confidence: high）
  TP-12: _mock_judge_response() の返り値が必須キーを含むこと
  TP-13: _mock_judge_response() セクション見出しが明らかに無関係な場合はLevel3欠落（dis_b03_a2）
  TP-14: _heading_is_unrelated() 2文字共通漢字があれば無関係判定しない（dis_b03_a2）

実行方法（プロジェクトルートから）:
    python3 -m pytest scripts/test_m3_prompt.py -v

作成者: Majiro-ns / 2026-03-14 / dis_b03_a6 + dis_b03_a2
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

import m3_gap_analysis_agent as m3
from m3_gap_analysis_agent import (
    SYSTEM_PROMPT,
    _build_user_prompt,
    _heading_is_unrelated,
    _mock_judge_response,
)


def _make_section(text: str = "", tables: list | None = None) -> m3.SectionData:
    """テスト用 SectionData を生成するヘルパー。"""
    return m3.SectionData(
        section_id="SEC-001",
        heading="人的資本",
        text=text,
        tables=tables or [],
    )


def _make_law_entry(
    change_type: str = "追加必須",
    title: str = "内閣府令改正2024",
) -> m3.LawEntry:
    """テスト用 LawEntry を生成するヘルパー。"""
    return m3.LawEntry(
        id="HC_001",
        title=title,
        category="人的資本",
        disclosure_items=["人的資本方針"],
        change_type=change_type,
        summary="人的資本開示の義務化",
        effective_from="2024-03-31",
        source="https://example.com/law",
        source_confirmed=True,
    )


# ===========================================================================
# TP-1〜3: SYSTEM_PROMPT の内容確認
# ===========================================================================

class TestSystemPrompt(unittest.TestCase):
    """SYSTEM_PROMPT の改善内容を検証する。"""

    def test_tp1_has_gap_criteria_in_system_prompt(self):
        """TP-1: SYSTEM_PROMPT に has_gap 判定基準（true/false の説明）が含まれること"""
        self.assertIn("has_gap: true", SYSTEM_PROMPT, "has_gap: true の基準が含まれること")
        self.assertIn("has_gap: false", SYSTEM_PROMPT, "has_gap: false の基準が含まれること")
        # has_gap=true の条件: 不在・不十分・数値欠落
        self.assertTrue(
            "不在" in SYSTEM_PROMPT or "不十分" in SYSTEM_PROMPT,
            "has_gap=true の条件説明が含まれること",
        )

    def test_tp2_confidence_criteria_in_system_prompt(self):
        """TP-2: SYSTEM_PROMPT に confidence 高/中/低 の定義が含まれること"""
        self.assertIn("high（高）", SYSTEM_PROMPT, "high（高）の説明が含まれること")
        self.assertIn("medium（中）", SYSTEM_PROMPT, "medium（中）の説明が含まれること")
        self.assertIn("low（低）", SYSTEM_PROMPT, "low（低）の説明が含まれること")
        # 「明確な欠落」= ギャップでも high になることの記述
        self.assertIn("明確な欠落", SYSTEM_PROMPT, "has_gap=true でも high になりうる説明が含まれること")

    def test_tp3_json_format_example_in_system_prompt(self):
        """TP-3: SYSTEM_PROMPT に JSON フォーマット例が含まれること"""
        self.assertIn('"has_gap"', SYSTEM_PROMPT, "has_gap キーの例が含まれること")
        self.assertIn('"gap_description"', SYSTEM_PROMPT, "gap_description キーの例が含まれること")
        self.assertIn('"evidence_hint"', SYSTEM_PROMPT, "evidence_hint キーの例が含まれること")
        self.assertIn('"confidence"', SYSTEM_PROMPT, "confidence キーの例が含まれること")


# ===========================================================================
# TP-4〜7: _build_user_prompt() の内容確認
# ===========================================================================

class TestBuildUserPrompt(unittest.TestCase):
    """_build_user_prompt() の改善内容を検証する。"""

    def _make_prompt(
        self,
        text: str = "当社は多様性推進を重視しています。",
        disclosure_item: str = "多様性方針",
        tables: list | None = None,
    ) -> str:
        section = _make_section(text=text, tables=tables or [])
        law = _make_law_entry()
        return _build_user_prompt(section, disclosure_item, law)

    def test_tp4_starts_with_task_header(self):
        """TP-4: _build_user_prompt() が「【ギャップ判定タスク】」で始まること"""
        prompt = self._make_prompt()
        self.assertTrue(
            prompt.startswith("【ギャップ判定タスク】"),
            f"プロンプトが【ギャップ判定タスク】で始まること。先頭: {prompt[:50]!r}",
        )

    def test_tp5_contains_required_elements(self):
        """TP-5: _build_user_prompt() に開示項目・法令根拠・変更種別が含まれること"""
        prompt = self._make_prompt(disclosure_item="人的資本方針")
        self.assertIn("人的資本方針", prompt, "開示項目が含まれること")
        self.assertIn("内閣府令改正2024", prompt, "法令根拠が含まれること")
        self.assertIn("追加必須", prompt, "変更種別が含まれること")

    def test_tp6_table_annotation_when_table_exists(self):
        """TP-6: テーブルあり時に「テーブルデータ（数値情報として参照せよ）」注記が含まれること"""
        table = m3.TableData(
            caption="従業員数推移",
            rows=[["年度", "人数"], ["2023", "1000"], ["2024", "1050"]],
        )
        prompt = self._make_prompt(tables=[table])
        self.assertIn(
            "テーブルデータ（数値情報として参照せよ）",
            prompt,
            "テーブルあり時に数値情報注記が含まれること",
        )
        self.assertIn("従業員数推移", prompt, "テーブルキャプションが含まれること")

    def test_tp7_no_table_annotation_without_table(self):
        """TP-7: テーブルなし時に「テーブルデータ（数値情報として参照せよ）」注記が含まれないこと"""
        prompt = self._make_prompt(tables=[])
        self.assertNotIn(
            "テーブルデータ（数値情報として参照せよ）",
            prompt,
            "テーブルなし時にテーブル注記が含まれないこと",
        )


# ===========================================================================
# TP-8〜12: _mock_judge_response() の改善テスト
# ===========================================================================

class TestMockJudgeResponse(unittest.TestCase):
    """_mock_judge_response() の改善内容を検証する。"""

    REQUIRED_KEYS = {"has_gap", "gap_description", "evidence_hint", "confidence"}

    def test_tp12_returns_required_keys(self):
        """TP-12: 返り値に必須キー（has_gap/gap_description/evidence_hint/confidence）が含まれること"""
        section = _make_section("テスト")
        result = _mock_judge_response("多様性方針", section)
        self.assertTrue(
            self.REQUIRED_KEYS.issubset(result.keys()),
            f"必須キーが不足: {self.REQUIRED_KEYS - result.keys()}",
        )

    def test_tp8_numerical_item_with_number_and_keyword_is_no_gap(self):
        """TP-8: 数値系項目でテキスト内に数値+キーワードがあれば充足（has_gap=False, confidence=high）"""
        text = "当社の女性管理職比率は15.3%です。"
        section = _make_section(text)
        result = _mock_judge_response("女性管理職比率", section)
        self.assertFalse(result["has_gap"], "数値+キーワードがあれば has_gap=False")
        self.assertEqual(result["confidence"], "high", "充足確実なら confidence=high")
        self.assertIsNone(result["gap_description"], "充足時は gap_description=None")

    def test_tp9_numerical_item_without_number_is_gap(self):
        """TP-9: 数値系項目でキーワードがない場合ギャップ判定（has_gap=True）"""
        text = "当社は多様性を重視しています。人材育成に取り組んでいます。"
        section = _make_section(text)
        result = _mock_judge_response("従業員数", section)
        self.assertTrue(result["has_gap"], "数値もキーワードもなければ has_gap=True")
        self.assertIsNotNone(result["gap_description"])

    def test_tp10_qualitative_item_with_keyword_is_no_gap(self):
        """TP-10: 定性系項目でキーワードありは充足（has_gap=False, confidence=medium）"""
        text = "当社のサステナビリティ方針として、環境・社会・ガバナンスへの取り組みを推進します。"
        section = _make_section(text)
        result = _mock_judge_response("サステナビリティ方針", section)
        self.assertFalse(result["has_gap"], "キーワードありなら has_gap=False")
        self.assertEqual(result["confidence"], "medium", "定性系充足は confidence=medium")

    def test_tp11_qualitative_item_without_keyword_is_gap(self):
        """TP-11: 定性系項目でキーワードなしはギャップ（has_gap=True, confidence=high）"""
        text = "当社は積極的な事業展開を行っています。売上は前年比110%でした。"
        section = _make_section(text)
        result = _mock_judge_response("人的資本方針", section)
        self.assertTrue(result["has_gap"], "キーワードなしなら has_gap=True")
        self.assertEqual(result["confidence"], "high", "定性系ギャップは confidence=high")

    def test_tp_numerical_item_without_keyword_is_gap(self):
        """TP-9b: 数値系項目でテキストに数値はあるがキーワードがない場合もギャップ"""
        text = "売上は100億円、営業利益は10億円でした。"  # 数値あり・給与キーワードなし
        section = _make_section(text)
        result = _mock_judge_response("給与", section)
        self.assertTrue(result["has_gap"], "キーワードがなければ数値があってもギャップ")

    def test_tp13_unrelated_heading_returns_gap_high(self):
        """TP-13: セクション見出しが開示項目と明らかに無関係な場合はLevel3欠落（confidence=high）"""
        section = m3.SectionData(
            section_id="SEC-002",
            heading="設備の状況",
            text="当社は工場の設備に継続的に投資しています。",
            tables=[],
        )
        result = _mock_judge_response("女性管理職比率", section)
        self.assertTrue(result["has_gap"], "無関係な見出しでは has_gap=True")
        self.assertEqual(result["confidence"], "high", "無関係な見出しは confidence=high")

    def test_tp14_ngram_overlap_prevents_unrelated_classification(self):
        """TP-14: 2文字共通漢字がある場合は _heading_is_unrelated=False であること"""
        # 「設備投資の状況」と「設備の状況」は「設備」を共通に持つ → 関連あり
        self.assertFalse(
            _heading_is_unrelated("設備投資の状況", ["設備投資の状況"], "設備の状況"),
            "共通2文字漢字がある場合は無関係と判定しない",
        )
        # 「財務諸表」と「財務情報管理方針」は「財務」共通 → 関連あり
        self.assertFalse(
            _heading_is_unrelated("財務情報管理方針", ["財務情報管理方針"], "財務諸表"),
            "「財務」共通の場合は無関係と判定しない",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
