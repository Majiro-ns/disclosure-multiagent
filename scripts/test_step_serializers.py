"""test_step_serializers.py
==========================
step_serializers.py の単体テスト。

モックデータで serialize_m1〜serialize_m5 の出力形式を検証する。
cmd_360k_a3f にて作成 (2026-03-14)。
"""

from __future__ import annotations

import sys
import os
import unittest
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import MagicMock

# scripts/ を sys.path に追加（conftest.py で設定済みだがスタンドアロンでも動くよう保険）
_SCRIPTS_DIR = os.path.dirname(__file__)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from step_serializers import (
    serialize_m1,
    serialize_m2,
    serialize_m3,
    serialize_m4,
    serialize_m5,
    _proposal_quality_status,
)


# ─────────────────────────────────────────────────────────
# テスト用モックデータ生成ヘルパー
# ─────────────────────────────────────────────────────────

def _make_section(section_id: str, heading: str, text: str):
    s = MagicMock()
    s.section_id = section_id
    s.heading = heading
    s.text = text
    return s


def _make_structured_report(sections=None, company_name="テスト商事", fiscal_year=2025):
    r = MagicMock()
    r.company_name = company_name
    r.fiscal_year = fiscal_year
    r.sections = sections or []
    return r


def _make_law_entry(law_id: str, title: str, category: str, source_confirmed: bool = True):
    e = MagicMock()
    e.id = law_id
    e.title = title
    e.category = category
    e.source_confirmed = source_confirmed
    return e


def _make_law_context(entries=None, warnings=None):
    ctx = MagicMock()
    ctx.applicable_entries = entries or []
    ctx.warnings = warnings or []
    return ctx


def _make_gap_item(gap_id: str, change_type: str = "追加必須", has_gap: bool = True,
                   confidence: str = "high", gap_description: Optional[str] = None):
    g = MagicMock()
    g.gap_id = gap_id
    g.section_heading = "人的資本"
    g.change_type = change_type
    g.has_gap = has_gap
    g.confidence = confidence
    g.gap_description = gap_description
    return g


def _make_gap_analysis_result(total_gaps: int = 3, gaps=None, by_change_type=None):
    r = MagicMock()
    r.summary = MagicMock()
    r.summary.total_gaps = total_gaps
    r.summary.by_change_type = by_change_type or {"追加必須": 2, "修正推奨": 1, "参考": 0}
    r.gaps = gaps or []
    r.no_gap_items = []
    return r


def _make_proposal(level: str, text: str, status: str = "pass"):
    p = MagicMock()
    p.level = level
    p.text = text
    p.status = status
    return p


def _make_proposal_set(gap_id: str, disclosure_item: str = "テスト項目",
                       matsu_status: str = "pass", take_status: str = "pass",
                       ume_status: str = "pass"):
    ps = MagicMock()
    ps.gap_id = gap_id
    ps.disclosure_item = disclosure_item
    ps.matsu = _make_proposal("松", "松の提案文" * 5, matsu_status)
    ps.take = _make_proposal("竹", "竹の提案文" * 5, take_status)
    ps.ume = _make_proposal("梅", "梅の提案文" * 5, ume_status)
    return ps


# ─────────────────────────────────────────────────────────
# serialize_m1 テスト
# ─────────────────────────────────────────────────────────

class TestSerializeM1(unittest.TestCase):

    def test_empty_sections(self):
        """セクションなしのレポートをシリアライズできること。"""
        report = _make_structured_report(sections=[])
        result = serialize_m1(report)

        self.assertEqual(result["company_name"], "テスト商事")
        self.assertEqual(result["fiscal_year"], 2025)
        self.assertEqual(result["total_sections"], 0)
        self.assertEqual(result["total_chars"], 0)
        self.assertEqual(result["sections"], [])

    def test_single_section(self):
        """1セクションのレポートをシリアライズできること。"""
        text = "人的資本に関する情報を記載します。" * 10
        section = _make_section("sec_001", "人的資本", text)
        report = _make_structured_report(sections=[section])

        result = serialize_m1(report)

        self.assertEqual(result["total_sections"], 1)
        self.assertEqual(result["total_chars"], len(text))
        self.assertEqual(len(result["sections"]), 1)

        sec = result["sections"][0]
        self.assertEqual(sec["id"], "sec_001")
        self.assertEqual(sec["heading"], "人的資本")
        self.assertEqual(sec["char_count"], len(text))

    def test_preview_truncated_at_200_chars(self):
        """previewが200文字でカットされること。"""
        text = "あ" * 300
        section = _make_section("sec_001", "テスト", text)
        report = _make_structured_report(sections=[section])

        result = serialize_m1(report)
        self.assertEqual(result["sections"][0]["preview"], "あ" * 200)

    def test_preview_short_text_not_truncated(self):
        """短いテキストはpreviewが切り捨てられないこと。"""
        text = "短いテキスト"
        section = _make_section("sec_001", "テスト", text)
        report = _make_structured_report(sections=[section])

        result = serialize_m1(report)
        self.assertEqual(result["sections"][0]["preview"], text)

    def test_multiple_sections_total_chars(self):
        """複数セクションの文字数合計が正しいこと。"""
        s1 = _make_section("sec_001", "セクション1", "テキスト1" * 10)
        s2 = _make_section("sec_002", "セクション2", "テキスト2" * 20)
        report = _make_structured_report(sections=[s1, s2])

        result = serialize_m1(report)
        expected_total = len("テキスト1" * 10) + len("テキスト2" * 20)
        self.assertEqual(result["total_chars"], expected_total)
        self.assertEqual(result["total_sections"], 2)

    def test_company_name_and_fiscal_year(self):
        """company_nameとfiscal_yearが正しく含まれること。"""
        report = _make_structured_report(company_name="サンプル株式会社", fiscal_year=2024)
        result = serialize_m1(report)
        self.assertEqual(result["company_name"], "サンプル株式会社")
        self.assertEqual(result["fiscal_year"], 2024)


# ─────────────────────────────────────────────────────────
# serialize_m2 テスト
# ─────────────────────────────────────────────────────────

class TestSerializeM2(unittest.TestCase):

    def test_empty_entries(self):
        """エントリなしのLawContextをシリアライズできること。"""
        ctx = _make_law_context(entries=[], warnings=[])
        result = serialize_m2(ctx)

        self.assertEqual(result["total_entries"], 0)
        self.assertEqual(result["categories"], {})
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["entries"], [])

    def test_category_aggregation(self):
        """カテゴリ別件数が正しく集計されること。"""
        entries = [
            _make_law_entry("e1", "法令A", "人的資本"),
            _make_law_entry("e2", "法令B", "人的資本"),
            _make_law_entry("e3", "法令C", "SSBJ"),
        ]
        ctx = _make_law_context(entries=entries)
        result = serialize_m2(ctx)

        self.assertEqual(result["total_entries"], 3)
        self.assertEqual(result["categories"]["人的資本"], 2)
        self.assertEqual(result["categories"]["SSBJ"], 1)

    def test_entries_fields(self):
        """entriesの各フィールドが正しく含まれること。"""
        entry = _make_law_entry("hc-001", "人的資本テスト法令", "人的資本", source_confirmed=False)
        ctx = _make_law_context(entries=[entry])
        result = serialize_m2(ctx)

        e = result["entries"][0]
        self.assertEqual(e["law_id"], "hc-001")
        self.assertEqual(e["title"], "人的資本テスト法令")
        self.assertEqual(e["category"], "人的資本")
        self.assertFalse(e["source_confirmed"])

    def test_warnings_included(self):
        """warningsが正しく含まれること。"""
        warnings = ["⚠️ 重要カテゴリのエントリが0件: 人的資本ガイダンス"]
        ctx = _make_law_context(warnings=warnings)
        result = serialize_m2(ctx)
        self.assertEqual(result["warnings"], warnings)


# ─────────────────────────────────────────────────────────
# serialize_m3 テスト
# ─────────────────────────────────────────────────────────

class TestSerializeM3(unittest.TestCase):

    def test_empty_gaps(self):
        """gapsなしのGapAnalysisResultをシリアライズできること。"""
        gap_result = _make_gap_analysis_result(total_gaps=0, gaps=[], by_change_type={})
        result = serialize_m3(gap_result)

        self.assertEqual(result["total_gaps"], 0)
        self.assertEqual(result["gaps"], [])

    def test_by_change_type(self):
        """by_change_typeが正しく含まれること。"""
        by_ct = {"追加必須": 5, "修正推奨": 3, "参考": 1}
        gap_result = _make_gap_analysis_result(total_gaps=9, by_change_type=by_ct)
        result = serialize_m3(gap_result)

        self.assertEqual(result["by_change_type"], by_ct)
        self.assertEqual(result["total_gaps"], 9)

    def test_gap_fields(self):
        """gapの各フィールドが正しく含まれること。"""
        gap = _make_gap_item("GAP-001", change_type="追加必須", has_gap=True,
                             confidence="high", gap_description="記載が不十分です。")
        gap_result = _make_gap_analysis_result(gaps=[gap])
        result = serialize_m3(gap_result)

        g = result["gaps"][0]
        self.assertEqual(g["gap_id"], "GAP-001")
        self.assertEqual(g["section"], "人的資本")
        self.assertEqual(g["change_type"], "追加必須")
        self.assertTrue(g["has_gap"])
        self.assertEqual(g["confidence"], "high")
        self.assertEqual(g["description"], "記載が不十分です。")

    def test_description_truncated_at_100_chars(self):
        """descriptionが100文字でカットされること。"""
        long_desc = "説明文" * 50  # 150文字
        gap = _make_gap_item("GAP-001", gap_description=long_desc)
        gap_result = _make_gap_analysis_result(gaps=[gap])
        result = serialize_m3(gap_result)

        self.assertEqual(len(result["gaps"][0]["description"]), 100)

    def test_none_gap_description_becomes_empty_string(self):
        """gap_descriptionがNoneの場合、空文字になること。"""
        gap = _make_gap_item("GAP-001", gap_description=None)
        gap_result = _make_gap_analysis_result(gaps=[gap])
        result = serialize_m3(gap_result)

        self.assertEqual(result["gaps"][0]["description"], "")


# ─────────────────────────────────────────────────────────
# serialize_m4 テスト
# ─────────────────────────────────────────────────────────

class TestSerializeM4(unittest.TestCase):

    def test_empty_proposals(self):
        """提案なしのリストをシリアライズできること。"""
        result = serialize_m4([])
        self.assertEqual(result["total_proposals"], 0)
        self.assertEqual(result["proposals"], [])

    def test_proposal_fields(self):
        """proposalの各フィールドが正しく含まれること。"""
        ps = _make_proposal_set("GAP-001", disclosure_item="平均年間給与")
        result = serialize_m4([ps])

        p = result["proposals"][0]
        self.assertEqual(p["gap_id"], "GAP-001")
        self.assertEqual(p["disclosure_item"], "平均年間給与")
        self.assertIn("matsu_preview", p)
        self.assertIn("take_preview", p)
        self.assertIn("ume_preview", p)
        self.assertIn("quality_status", p)

    def test_preview_truncated_at_80_chars(self):
        """各previewが80文字でカットされること。"""
        ps = _make_proposal_set("GAP-001")
        ps.matsu.text = "松" * 100
        ps.take.text = "竹" * 100
        ps.ume.text = "梅" * 100

        result = serialize_m4([ps])
        p = result["proposals"][0]
        self.assertEqual(len(p["matsu_preview"]), 80)
        self.assertEqual(len(p["take_preview"]), 80)
        self.assertEqual(len(p["ume_preview"]), 80)

    def test_quality_status_pass(self):
        """全て pass の場合 quality_status が 'pass' になること。"""
        ps = _make_proposal_set("GAP-001", matsu_status="pass", take_status="pass", ume_status="pass")
        result = serialize_m4([ps])
        self.assertEqual(result["proposals"][0]["quality_status"], "pass")

    def test_quality_status_warn(self):
        """いずれかが warn の場合 quality_status が 'warn' になること。"""
        ps = _make_proposal_set("GAP-001", matsu_status="pass", take_status="warn", ume_status="pass")
        result = serialize_m4([ps])
        self.assertEqual(result["proposals"][0]["quality_status"], "warn")

    def test_quality_status_fail(self):
        """いずれかが fail の場合 quality_status が 'fail' になること。"""
        ps = _make_proposal_set("GAP-001", matsu_status="pass", take_status="fail", ume_status="warn")
        result = serialize_m4([ps])
        self.assertEqual(result["proposals"][0]["quality_status"], "fail")

    def test_total_proposals_count(self):
        """total_proposalsが正しく返ること。"""
        proposals = [_make_proposal_set(f"GAP-{i:03d}") for i in range(5)]
        result = serialize_m4(proposals)
        self.assertEqual(result["total_proposals"], 5)


# ─────────────────────────────────────────────────────────
# _proposal_quality_status テスト
# ─────────────────────────────────────────────────────────

class TestProposalQualityStatus(unittest.TestCase):

    def test_all_pass(self):
        ps = _make_proposal_set("GAP-001", matsu_status="pass", take_status="pass", ume_status="pass")
        self.assertEqual(_proposal_quality_status(ps), "pass")

    def test_one_warn(self):
        ps = _make_proposal_set("GAP-001", matsu_status="warn", take_status="pass", ume_status="pass")
        self.assertEqual(_proposal_quality_status(ps), "warn")

    def test_one_fail_overrides_warn(self):
        ps = _make_proposal_set("GAP-001", matsu_status="fail", take_status="warn", ume_status="pass")
        self.assertEqual(_proposal_quality_status(ps), "fail")

    def test_all_fail(self):
        ps = _make_proposal_set("GAP-001", matsu_status="fail", take_status="fail", ume_status="fail")
        self.assertEqual(_proposal_quality_status(ps), "fail")


# ─────────────────────────────────────────────────────────
# serialize_m5 テスト
# ─────────────────────────────────────────────────────────

class TestSerializeM5(unittest.TestCase):

    def test_empty_string(self):
        """空文字列のシリアライズ。"""
        result = serialize_m5("")
        self.assertEqual(result["total_chars"], 0)
        self.assertEqual(result["total_lines"], 0)
        self.assertEqual(result["preview"], "")
        self.assertEqual(result["full_text"], "")

    def test_total_chars(self):
        """total_charsが文字数を正しく返すこと。"""
        md = "# タイトル\n\n本文テキスト。\n"
        result = serialize_m5(md)
        self.assertEqual(result["total_chars"], len(md))

    def test_total_lines(self):
        """total_linesが行数を正しく返すこと。"""
        md = "line1\nline2\nline3"  # 3行（末尾改行なし）
        result = serialize_m5(md)
        self.assertEqual(result["total_lines"], 3)

    def test_total_lines_with_trailing_newline(self):
        """末尾改行ありの行数カウント。"""
        md = "line1\nline2\n"  # 改行2つ → 3行とみなす
        result = serialize_m5(md)
        self.assertEqual(result["total_lines"], 3)

    def test_preview_truncated_at_1000_chars(self):
        """previewが1000文字でカットされること。"""
        md = "あ" * 2000
        result = serialize_m5(md)
        self.assertEqual(result["preview"], "あ" * 1000)

    def test_preview_short_text_not_truncated(self):
        """短いMarkdownはpreviewが切り捨てられないこと。"""
        md = "# タイトル\n内容"
        result = serialize_m5(md)
        self.assertEqual(result["preview"], md)

    def test_full_text_preserved(self):
        """full_textに全文が含まれること。"""
        md = "テスト" * 1000
        result = serialize_m5(md)
        self.assertEqual(result["full_text"], md)

    def test_keys_present(self):
        """必須キーが全て含まれること。"""
        result = serialize_m5("テスト")
        for key in ("total_chars", "total_lines", "preview", "full_text"):
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
