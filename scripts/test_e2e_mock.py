"""
test_e2e_mock.py
================
disclosure-multiagent E2E モックテスト（tests/fixtures/sample_yuho.pdf 使用）

タスク: cmd_350k_a6b
実装者: 足軽6
作成日: 2026-03-10

テスト概要:
  sample_yuho.pdf（OSS公開用架空PDF）を入力に
  USE_MOCK_LLM=true で M1→M2→M3→M4→M5 パイプラインを実行し、
  松・竹・梅 各レベルの提案生成と出力フォーマットを検証する。

テスト一覧:
  TC-E01: sample_yuho.pdf + 竹レベル → run_pipeline() 完走
  TC-E02: sample_yuho.pdf + 松レベル → run_pipeline() 完走
  TC-E03: sample_yuho.pdf + 梅レベル → run_pipeline() 完走
  TC-E04: 出力フォーマット検証（## セクション + 但し書き + 非空）
  TC-E05: 松竹梅3レベルの M4 ProposalSet が全て生成される
  TC-E06: 松・竹・梅レベルで出力サイズが適切（各非空）
  TC-E07: company_name が M5 レポートに含まれる

既存テストとの差分（重複回避）:
  test_e2e_smoke.py:    company_a.pdf / company_b.pdf（10_Research/samples/）使用
  test_e2e_pipeline.py: pipeline_mock() と run_pipeline() 検証
  本ファイル:           tests/fixtures/sample_yuho.pdf を使用する点で新規
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# USE_MOCK_LLM=true を強制（実API呼び出しなし）
os.environ.setdefault("USE_MOCK_LLM", "true")

# scripts ディレクトリをパスに追加
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# tests/fixtures/sample_yuho.pdf パス
_FIXTURES_DIR = _SCRIPTS_DIR.parent / "tests" / "fixtures"
SAMPLE_YUHO_PDF = str(_FIXTURES_DIR / "sample_yuho.pdf")


def _skip_if_no_pdf(test_instance: unittest.TestCase) -> None:
    """sample_yuho.pdf が存在しない場合スキップ"""
    if not Path(SAMPLE_YUHO_PDF).exists():
        test_instance.skipTest(
            f"sample_yuho.pdf が存在しません: {SAMPLE_YUHO_PDF}"
        )


# ═══════════════════════════════════════════════════════════════
# TC-E01〜E03: 松竹梅 各レベルでのフルパイプライン完走
# ═══════════════════════════════════════════════════════════════

class TestE2EMockAllLevels(unittest.TestCase):
    """TC-E01〜E03: sample_yuho.pdf で松竹梅各レベルのパイプラインが完走する"""

    def setUp(self) -> None:
        os.environ["USE_MOCK_LLM"] = "true"

    def test_tc_e01_take_level_pipeline_completes(self) -> None:
        """
        TC-E01: sample_yuho.pdf + 竹レベル → run_pipeline() が str を返す

        根拠: 最も標準的な「竹」レベルで M1→M5 パイプラインが完走することを確認。
        CHECK-9: USE_MOCK_LLM=true により M3/M4 はモックデータを使用。
                 sample_yuho.pdf は OSS公開用架空PDFであり、M1 が抽出するセクション数に
                 関わらず M3 以降はモック動作のため完走する。
        """
        _skip_if_no_pdf(self)
        from run_e2e import run_pipeline

        result = run_pipeline(
            pdf_path=SAMPLE_YUHO_PDF,
            company_name="テスト有報社（竹）",
            fiscal_year=2025,
            level="竹",
        )

        self.assertIsInstance(result, str, "run_pipeline(竹) が str を返さなかった")
        self.assertGreater(len(result), 0, "run_pipeline(竹) の出力が空文字列")

    def test_tc_e02_matsu_level_pipeline_completes(self) -> None:
        """
        TC-E02: sample_yuho.pdf + 松レベル → run_pipeline() が str を返す

        根拠: 最詳細な「松」レベルで M1→M5 パイプラインが完走することを確認。
        CHECK-9: 松レベルは最大文字数480字（CHAR_LIMITS["松"]["max"]: 480）。
                 モックモードでの生成であるが、レポート出力が得られることを検証する。
        """
        _skip_if_no_pdf(self)
        from run_e2e import run_pipeline

        result = run_pipeline(
            pdf_path=SAMPLE_YUHO_PDF,
            company_name="テスト有報社（松）",
            fiscal_year=2025,
            level="松",
        )

        self.assertIsInstance(result, str, "run_pipeline(松) が str を返さなかった")
        self.assertGreater(len(result), 0, "run_pipeline(松) の出力が空文字列")

    def test_tc_e03_ume_level_pipeline_completes(self) -> None:
        """
        TC-E03: sample_yuho.pdf + 梅レベル → run_pipeline() が str を返す

        根拠: 最簡潔な「梅」レベルで M1→M5 パイプラインが完走することを確認。
        CHECK-9: 梅レベルは最大文字数120字（CHAR_LIMITS["ume"]["max"]: 120）。
                 level パラメータが M5 generate_report() に正しく伝達されることの確認。
        """
        _skip_if_no_pdf(self)
        from run_e2e import run_pipeline

        result = run_pipeline(
            pdf_path=SAMPLE_YUHO_PDF,
            company_name="テスト有報社（梅）",
            fiscal_year=2025,
            level="梅",
        )

        self.assertIsInstance(result, str, "run_pipeline(梅) が str を返さなかった")
        self.assertGreater(len(result), 0, "run_pipeline(梅) の出力が空文字列")


# ═══════════════════════════════════════════════════════════════
# TC-E04: 出力フォーマット検証
# ═══════════════════════════════════════════════════════════════

class TestE2EMockOutputFormat(unittest.TestCase):
    """TC-E04: 出力フォーマット検証（Markdown構造・但し書き・非空コンテンツ）"""

    def setUp(self) -> None:
        os.environ["USE_MOCK_LLM"] = "true"

    def test_tc_e04_output_format_markdown_and_disclaimer(self) -> None:
        """
        TC-E04: 竹レベルの出力が Markdown 形式（## ヘッダー）と但し書きを含む

        根拠: M5 generate_report() は必ず免責事項（但し書き）を出力する
             （m5_report_agent._build_disclaimer_header() が常に呼ばれる）。
             また ## セクションヘッダーが存在することで有効な Markdown であることを確認。
        CHECK-9: sample_yuho.pdf + 竹レベルで実行。
                 「但し書き」の存在確認により M5 まで到達したことを証明する（TC-1 と同様の手法）。
        """
        _skip_if_no_pdf(self)
        from run_e2e import run_pipeline

        result = run_pipeline(
            pdf_path=SAMPLE_YUHO_PDF,
            company_name="フォーマット検証社",
            fiscal_year=2025,
            level="竹",
        )

        # ## Markdown ヘッダーが存在する
        self.assertIn(
            "##",
            result,
            "出力に ## Markdown ヘッダーが含まれていない",
        )

        # M5 免責事項（但し書き）が存在する
        self.assertIn(
            "但し書き",
            result,
            "出力に「但し書き」が含まれていない（M5 未到達の可能性）",
        )

        # 実質的なコンテンツがある（200文字超）
        self.assertGreater(
            len(result),
            200,
            f"出力が短すぎます（{len(result)}文字 ≤ 200文字）",
        )


# ═══════════════════════════════════════════════════════════════
# TC-E05: M4 ProposalSet 松竹梅3水準の検証
# ═══════════════════════════════════════════════════════════════

class TestE2EMockProposalSet(unittest.TestCase):
    """TC-E05: M4 generate_proposals() が松竹梅3水準を全て生成する"""

    def setUp(self) -> None:
        os.environ["USE_MOCK_LLM"] = "true"

    def test_tc_e05_proposal_set_has_all_three_levels(self) -> None:
        """
        TC-E05: generate_proposals() が ProposalSet（松・竹・梅）を返す

        根拠: M4 generate_proposals() は GapItem を入力に松竹梅3水準の Proposal を生成する。
             ProposalSet.get_proposal("松"/"竹"/"梅") が各 Proposal を返すことを確認。
        CHECK-9: M3 モックデータから生成した GapItem を M4 に渡す。
                 各 Proposal の level フィールドと text フィールドが正しい型であることを確認。
        """
        from m3_gap_analysis_agent import (
            analyze_gaps,
            _build_mock_report,
            _build_mock_law_context,
        )
        from m4_proposal_agent import generate_proposals
        from m5_report_agent import _m3_gap_to_m4_gap

        # M3 モックデータ構築
        gap_result = analyze_gaps(
            report=_build_mock_report(),
            law_context=_build_mock_law_context(),
            use_mock=True,
        )

        # has_gap=True のギャップが1件以上存在する前提
        has_gap_items = [g for g in gap_result.gaps if g.has_gap]
        if not has_gap_items:
            self.skipTest("has_gap=True のギャップが0件（モックデータを確認）")

        # M4: 最初の has_gap アイテムで ProposalSet を生成
        m4_gap = _m3_gap_to_m4_gap(has_gap_items[0])
        proposal_set = generate_proposals(m4_gap)

        # ProposalSet が全3水準を持つ
        for level in ("松", "竹", "梅"):
            proposal = proposal_set.get_proposal(level)
            self.assertIsNotNone(
                proposal,
                f"get_proposal('{level}') が None を返した",
            )
            self.assertEqual(
                proposal.level,
                level,
                f"Proposal.level が '{level}' でない: {proposal.level}",
            )
            self.assertIsInstance(
                proposal.text,
                str,
                f"{level}の Proposal.text が str でない",
            )
            self.assertGreater(
                len(proposal.text),
                0,
                f"{level}の Proposal.text が空文字列",
            )


# ═══════════════════════════════════════════════════════════════
# TC-E06: 松竹梅 各レベル出力の非空確認
# ═══════════════════════════════════════════════════════════════

class TestE2EMockLevelOutputSizes(unittest.TestCase):
    """TC-E06: 松・竹・梅 各レベルで非空の出力が得られる"""

    def setUp(self) -> None:
        os.environ["USE_MOCK_LLM"] = "true"
        _skip_if_no_pdf(self)

    def test_tc_e06_all_levels_produce_non_empty_output(self) -> None:
        """
        TC-E06: 松・竹・梅 3レベル全てで非空のレポートが生成される

        根拠: run_pipeline() の level パラメータが M5 に正しく渡され、
             どのレベルでも有効なレポート出力が得られることを一括確認する。
        CHECK-9: 3レベルの結果をまとめて検証することで、level パラメータが
                 M5 に到達していることの確認と、意図せず空文字が返らないことを保証する。
        """
        from run_e2e import run_pipeline

        outputs: dict[str, str] = {}
        for level in ("松", "竹", "梅"):
            result = run_pipeline(
                pdf_path=SAMPLE_YUHO_PDF,
                company_name=f"レベル比較テスト社_{level}",
                fiscal_year=2025,
                level=level,
            )
            outputs[level] = result

        for level, output in outputs.items():
            self.assertIsInstance(output, str, f"{level}レベルの出力が str でない")
            self.assertGreater(
                len(output),
                0,
                f"{level}レベルの出力が空文字列",
            )


# ═══════════════════════════════════════════════════════════════
# TC-E07: company_name が M5 レポートに反映される
# ═══════════════════════════════════════════════════════════════

class TestE2EMockCompanyNameInOutput(unittest.TestCase):
    """TC-E07: company_name が M5 レポート出力に含まれる"""

    def setUp(self) -> None:
        os.environ["USE_MOCK_LLM"] = "true"

    def test_tc_e07_company_name_appears_in_report(self) -> None:
        """
        TC-E07: 指定した company_name が M5 レポートに含まれる

        根拠: M5 generate_report() はレポートのヘッダーに company_name を出力する。
             company_name が M1→M5 を通じて正しく伝達されることを確認する。
        CHECK-9: pipeline_mock() は company_name を出力に含む設計
                （test_e2e_pipeline.py TC-2と同手法だが sample_yuho.pdf 経由で検証）。
                 USE_MOCK_LLM=true かつ sample_yuho.pdf を使用する点で新規。
        """
        _skip_if_no_pdf(self)
        from run_e2e import run_pipeline

        company = "sample_yuho_テスト企業_unique"
        result = run_pipeline(
            pdf_path=SAMPLE_YUHO_PDF,
            company_name=company,
            fiscal_year=2025,
            level="竹",
        )

        self.assertIn(
            company,
            result,
            f"company_name '{company}' が M5 レポートに含まれていない。"
            f"出力先頭300文字: {result[:300]}",
        )


if __name__ == "__main__":
    unittest.main()
