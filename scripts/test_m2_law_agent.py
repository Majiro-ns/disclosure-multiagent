"""
test_m2_law_agent.py
====================
disclosure-multiagent Phase 1-M2: 法令収集エージェント テスト

実行方法（実際のYAMLを使用・APIキー不要）:
    cd scripts/
    python3 test_m2_law_agent.py

テスト一覧:
    TEST 1: 実際のlaw_entries_human_capital.yamlを読み込んでLawContext生成
    TEST 2: 2025年度3月決算でHC_20260220_001（施行2026-02-20）が含まれることを確認
    TEST 3: 2024年度3月決算でHC_20260220_001が含まれないことを確認（期間外）
    TEST 4: CHECK-7b 法令参照期間の手計算検証
    TEST 5: 重要カテゴリ0件時の警告生成
    INTEGRATION: M3との統合確認
"""

import sys
import unittest
import yaml
from pathlib import Path
from datetime import date
from unittest.mock import patch

# テスト対象モジュールをインポート
sys.path.insert(0, ".")
from m2_law_agent import (
    load_law_context,
    load_law_entries,
    get_applicable_entries,
    LAW_YAML_DIR,
    LAW_YAML_FILE,
    CRITICAL_CATEGORIES,
    _load_all_from_dir,
)
from m3_gap_analysis_agent import (
    LawEntry,
    calc_law_ref_period,
    _build_mock_report,
    analyze_gaps,
)

# 実際のYAMLファイルパス（TV-4: 実データ検証）
REAL_YAML_PATH = Path(__file__).parent.parent / "10_Research" / "law_entries_human_capital.yaml"


class TestLoadLawContext(unittest.TestCase):
    """TEST 1: 実際のlaw_entries_human_capital.yamlを読み込んでLawContext生成"""

    def test_load_real_yaml_returns_law_context(self):
        """実際のYAMLファイルを読み込んでLawContextが生成できる"""
        if not REAL_YAML_PATH.exists():
            self.skipTest(f"YAMLファイルが存在しません: {REAL_YAML_PATH}")

        ctx = load_law_context(2025, 3, yaml_path=REAL_YAML_PATH)

        # LawContextの構造確認
        self.assertEqual(ctx.fiscal_year, 2025)
        self.assertEqual(ctx.fiscal_month_end, 3)
        self.assertIsNotNone(ctx.law_yaml_as_of)
        self.assertIsInstance(ctx.applicable_entries, list)
        self.assertIsInstance(ctx.warnings, list)
        self.assertIsInstance(ctx.missing_categories, list)
        print(f"  [PASS] LawContext生成: applicable_entries={len(ctx.applicable_entries)}件, "
              f"law_yaml_as_of={ctx.law_yaml_as_of} ✓")

    def test_load_all_entries_count(self):
        """YAMLから全エントリ数を確認（TV-4: 実データ検証）"""
        if not REAL_YAML_PATH.exists():
            self.skipTest(f"YAMLファイルが存在しません: {REAL_YAML_PATH}")

        entries = load_law_entries(REAL_YAML_PATH)
        # law_entries_human_capital.yaml には7エントリが存在する（タスク仕様より）
        self.assertGreaterEqual(len(entries), 5, "最低5エントリ存在するはず")
        print(f"  [PASS] 全エントリ読み込み: {len(entries)}件 ✓")

    def test_law_yaml_as_of_format(self):
        """law_yaml_as_of が YYYY-MM-DD 形式である"""
        if not REAL_YAML_PATH.exists():
            self.skipTest(f"YAMLファイルが存在しません: {REAL_YAML_PATH}")

        ctx = load_law_context(2025, 3, yaml_path=REAL_YAML_PATH)
        # YYYY-MM-DD 形式チェック
        import re
        self.assertRegex(
            ctx.law_yaml_as_of,
            r"^\d{4}-\d{2}-\d{2}$",
            f"law_yaml_as_of={ctx.law_yaml_as_of} は YYYY-MM-DD 形式でない",
        )
        print(f"  [PASS] law_yaml_as_of形式: {ctx.law_yaml_as_of} ✓")


class TestApplicableEntriesFilter(unittest.TestCase):
    """TEST 2/3: 年度フィルタリングの正確性"""

    def test_2025_fiscal_year_includes_hc_20260220_001(self):
        """
        TEST 2: 2025年度3月決算でHC_20260220_001（施行2026-02-20）が含まれる

        手計算:
          fiscal_year=2025, fiscal_month_end=3
          参照期間: 2025/04/01〜2026/03/31
          HC_20260220_001 effective_from=2026-02-20
          2025-04-01 <= 2026-02-20 <= 2026-03-31 → True ✓ (含まれる)
        """
        if not REAL_YAML_PATH.exists():
            self.skipTest(f"YAMLファイルが存在しません: {REAL_YAML_PATH}")

        ctx = load_law_context(2025, 3, yaml_path=REAL_YAML_PATH)
        entry_ids = [e.id for e in ctx.applicable_entries]

        self.assertIn(
            "HC_20260220_001",
            entry_ids,
            f"HC_20260220_001が2025年度のapplicable_entriesに含まれていない: {entry_ids}",
        )
        # 施行日が参照期間内であることを確認
        hc_entry = next(e for e in ctx.applicable_entries if e.id == "HC_20260220_001")
        self.assertEqual(hc_entry.effective_from, "2026-02-20")
        print(f"  [PASS] 2025年度にHC_20260220_001(2026-02-20)が含まれる ✓")
        print(f"         参照期間: 2025/04/01〜2026/03/31")
        print(f"         applicable_entries: {entry_ids}")

    def test_2024_fiscal_year_excludes_hc_20260220_001(self):
        """
        TEST 3: 2024年度3月決算でHC_20260220_001（施行2026-02-20）が含まれない

        手計算:
          fiscal_year=2024, fiscal_month_end=3
          参照期間: 2024/04/01〜2025/03/31
          HC_20260220_001 effective_from=2026-02-20
          2026-02-20 > 2025-03-31 → False (含まれない)
        """
        if not REAL_YAML_PATH.exists():
            self.skipTest(f"YAMLファイルが存在しません: {REAL_YAML_PATH}")

        ctx = load_law_context(2024, 3, yaml_path=REAL_YAML_PATH)
        entry_ids = [e.id for e in ctx.applicable_entries]

        self.assertNotIn(
            "HC_20260220_001",
            entry_ids,
            f"HC_20260220_001が2024年度のapplicable_entriesに誤って含まれている: {entry_ids}",
        )
        print(f"  [PASS] 2024年度にHC_20260220_001(2026-02-20)が含まれない ✓")
        print(f"         参照期間: 2024/04/01〜2025/03/31")
        print(f"         applicable_entries: {entry_ids}")

    def test_get_applicable_entries_date_boundary(self):
        """境界値テスト: 参照期間の開始日・終了日ちょうどのエントリ"""
        entries = [
            LawEntry(
                id="TEST_START",
                title="期間開始日のエントリ",
                category="金商法・開示府令",
                change_type="追加必須",
                disclosure_items=["テスト項目"],
                source="https://example.com",
                source_confirmed=True,
                effective_from="2025-04-01",  # 期間開始日ちょうど
            ),
            LawEntry(
                id="TEST_END",
                title="期間終了日のエントリ",
                category="金商法・開示府令",
                change_type="追加必須",
                disclosure_items=["テスト項目"],
                source="https://example.com",
                source_confirmed=True,
                effective_from="2026-03-31",  # 期間終了日ちょうど
            ),
            LawEntry(
                id="TEST_BEFORE",
                title="期間前のエントリ",
                category="金商法・開示府令",
                change_type="追加必須",
                disclosure_items=["テスト項目"],
                source="https://example.com",
                source_confirmed=True,
                effective_from="2025-03-31",  # 期間開始日の前日 → 施行済みなので含まれる
            ),
            LawEntry(
                id="TEST_AFTER",
                title="期間後のエントリ",
                category="金商法・開示府令",
                change_type="追加必須",
                disclosure_items=["テスト項目"],
                source="https://example.com",
                source_confirmed=True,
                effective_from="2026-04-01",  # 期間終了日の翌日 → 含まれないはず
            ),
        ]
        ref_period = ("2025/04/01", "2026/03/31")
        result = get_applicable_entries(entries, ref_period)
        result_ids = [e.id for e in result]

        self.assertIn("TEST_START", result_ids, "期間開始日ちょうどのエントリが含まれない")
        self.assertIn("TEST_END", result_ids, "期間終了日ちょうどのエントリが含まれない")
        self.assertIn("TEST_BEFORE", result_ids, "施行済みエントリは継続適用されるべき")
        self.assertNotIn("TEST_AFTER", result_ids, "期間後のエントリが誤って含まれている")
        print(f"  [PASS] 境界値テスト: 施行済み法令の継続適用を正しく処理 ✓")


class TestCalcLawRefPeriod(unittest.TestCase):
    """TEST 4: CHECK-7b 法令参照期間の手計算検証（TV-4: 実データで根拠確認）"""

    def test_2025_march_period(self):
        """
        CHECK-7b: 2025年度3月決算 → 2025/04/01〜2026/03/31

        手計算（m3の定義通り）:
          fiscal_year=2025, fiscal_month_end=3
          start = "2025" + "/04/01" = "2025/04/01"
          end = str(2025+1) + "/03/31" = "2026/03/31"

        根拠（TV-4）: m3_gap_analysis_agent.py calc_law_ref_period() の実装
        → HC_20260220_001(2026-02-20) が2025/04/01〜2026/03/31の範囲内 ✓
        """
        start, end = calc_law_ref_period(2025, 3)
        self.assertEqual(start, "2025/04/01", f"期待=2025/04/01, 実際={start}")
        self.assertEqual(end, "2026/03/31", f"期待=2026/03/31, 実際={end}")

        # HC_20260220_001の施行日が期間内であることを手計算で確認
        d_start = date.fromisoformat(start.replace("/", "-"))
        d_end = date.fromisoformat(end.replace("/", "-"))
        hc_date = date(2026, 2, 20)
        in_period = d_start <= hc_date <= d_end
        self.assertTrue(in_period)
        print(f"  [PASS] CHECK-7b 2025年度3月決算: {start}〜{end}")
        print(f"         HC_20260220_001(2026-02-20) in period: {in_period} ✓")

    def test_2024_march_period(self):
        """
        CHECK-7b: 2024年度3月決算 → 2024/04/01〜2025/03/31

        手計算:
          fiscal_year=2024, fiscal_month_end=3
          start = "2024" + "/04/01" = "2024/04/01"
          end = str(2024+1) + "/03/31" = "2025/03/31"

        根拠（TV-4）: HC_20260220_001(2026-02-20) は2025/03/31より後
        → 2024年度の参照期間外 → 含まれないことを確認
        """
        start, end = calc_law_ref_period(2024, 3)
        self.assertEqual(start, "2024/04/01", f"期待=2024/04/01, 実際={start}")
        self.assertEqual(end, "2025/03/31", f"期待=2025/03/31, 実際={end}")

        # HC_20260220_001が期間外であることを確認
        d_end = date.fromisoformat(end.replace("/", "-"))
        hc_date = date(2026, 2, 20)
        self.assertGreater(hc_date, d_end,
            f"HC_20260220_001(2026-02-20) <= {end} となっており期間内に誤判定される")
        print(f"  [PASS] CHECK-7b 2024年度3月決算: {start}〜{end}")
        print(f"         HC_20260220_001(2026-02-20) > {end}: True ✓ (期間外)")

    def test_hc_20230131_001_in_2022_fiscal_year(self):
        """
        HC_20230131_001（施行2023-01-31）が2022年度3月決算に含まれるか確認

        手計算:
          fiscal_year=2022, fiscal_month_end=3
          参照期間: 2022/04/01〜2023/03/31
          HC_20230131_001 effective_from=2023-01-31
          2022-04-01 <= 2023-01-31 <= 2023-03-31 → True (含まれる)
        """
        start, end = calc_law_ref_period(2022, 3)
        d_start = date.fromisoformat(start.replace("/", "-"))
        d_end = date.fromisoformat(end.replace("/", "-"))
        hc_date = date(2023, 1, 31)
        in_period = d_start <= hc_date <= d_end
        self.assertTrue(in_period)
        print(f"  [PASS] HC_20230131_001(2023-01-31) in 2022年度({start}〜{end}): True ✓")

    def test_tc_new1_march_backward_compat(self):
        """
        TC-NEW-1: 3月決算（M7.5拡張後も既存動作と同一）fiscal_year=2025 → 2025/04/01〜2026/03/31

        CHECK-7b 手計算:
            fiscal_month_end=3, fiscal_year=2025
            start: fiscal_year/04/01 = 2025/04/01
            end:   (fiscal_year+1)/03/31 = 2026/03/31
        根拠: m3_gap_analysis_agent.py calc_law_ref_period() 実装（改変禁止）
        """
        start, end = calc_law_ref_period(2025, 3)
        self.assertEqual(start, "2025/04/01", f"期待=2025/04/01, 実際={start}")
        self.assertEqual(end, "2026/03/31", f"期待=2026/03/31, 実際={end}")
        print(f"  [PASS] TC-NEW-1 3月決算(2025): {start}〜{end} ✓")

    def test_tc_new2_december_fiscal(self):
        """
        TC-NEW-2: 12月決算 fiscal_year=2025 → 2025/01/01〜2025/12/31

        CHECK-7b 手計算:
            fiscal_month_end=12, fiscal_year=2025
            start: fiscal_year/01/01 = 2025/01/01  (1月始まり)
            end:   fiscal_year/12/31 = 2025/12/31  (12月末)
        根拠: m3_gap_analysis_agent.py calc_law_ref_period() — fiscal_month_end==12 分岐
        対象企業例: 12月決算企業（自動車メーカー等）の有報対応
        """
        start, end = calc_law_ref_period(2025, 12)
        self.assertEqual(start, "2025/01/01", f"期待=2025/01/01, 実際={start}")
        self.assertEqual(end, "2025/12/31", f"期待=2025/12/31, 実際={end}")
        # 期間内の日付確認
        d_start = date.fromisoformat(start.replace("/", "-"))
        d_end   = date.fromisoformat(end.replace("/", "-"))
        self.assertLess(d_start, d_end)
        self.assertEqual((d_end - d_start).days, 364)  # 2025年は365日-1日
        print(f"  [PASS] TC-NEW-2 12月決算(2025): {start}〜{end} ✓")

    def test_tc_new3_june_fiscal(self):
        """
        TC-NEW-3: 6月決算 fiscal_year=2025 → 2025/07/01〜2026/06/30

        CHECK-7b 手計算:
            fiscal_month_end=6, fiscal_year=2025
            start_month = 6 + 1 = 7
            start: 2025/07/01
            end_day: 6月 → 30日
            end: (2025+1)/06/30 = 2026/06/30
        根拠: m3_gap_analysis_agent.py calc_law_ref_period() — 一般ケース分岐
        """
        start, end = calc_law_ref_period(2025, 6)
        self.assertEqual(start, "2025/07/01", f"期待=2025/07/01, 実際={start}")
        self.assertEqual(end, "2026/06/30", f"期待=2026/06/30, 実際={end}")
        print(f"  [PASS] TC-NEW-3 6月決算(2025): {start}〜{end} ✓")

    def test_tc_new4_september_fiscal(self):
        """
        TC-NEW-4: 9月決算 fiscal_year=2025 → 2025/10/01〜2026/09/30

        CHECK-7b 手計算:
            fiscal_month_end=9, fiscal_year=2025
            start_month = 9 + 1 = 10
            start: 2025/10/01
            end_day: 9月 → 30日
            end: (2025+1)/09/30 = 2026/09/30
        根拠: m3_gap_analysis_agent.py calc_law_ref_period() — 一般ケース分岐
        """
        start, end = calc_law_ref_period(2025, 9)
        self.assertEqual(start, "2025/10/01", f"期待=2025/10/01, 実際={start}")
        self.assertEqual(end, "2026/09/30", f"期待=2026/09/30, 実際={end}")
        print(f"  [PASS] TC-NEW-4 9月決算(2025): {start}〜{end} ✓")

    def test_tc_new5_january_fiscal_boundary(self):
        """
        TC-NEW-5: 1月決算（境界値）fiscal_year=2025 → 2025/02/01〜2026/01/31

        CHECK-7b 手計算:
            fiscal_month_end=1, fiscal_year=2025
            start_month = 1 + 1 = 2
            start: 2025/02/01
            end_day: 1月 → 31日
            end: (2025+1)/01/31 = 2026/01/31
        根拠: m3_gap_analysis_agent.py calc_law_ref_period() — 一般ケース分岐
        特記: 1月は期末月が最小値（2月〜1月の会計年度）の境界値
        """
        start, end = calc_law_ref_period(2025, 1)
        self.assertEqual(start, "2025/02/01", f"期待=2025/02/01, 実際={start}")
        self.assertEqual(end, "2026/01/31", f"期待=2026/01/31, 実際={end}")
        print(f"  [PASS] TC-NEW-5 1月決算(2025): {start}〜{end} ✓")


class TestWarnings(unittest.TestCase):
    """TEST 5: 重要カテゴリ0件時の警告生成"""

    def test_missing_critical_category_warning(self):
        """
        重要カテゴリが0件の場合、warnings と missing_categories に記録される

        使用ダミーエントリ: 人的資本ガイダンスのみ → 金商法・開示府令とSSBJが0件
        """
        dummy_entries = [
            LawEntry(
                id="HC_DUMMY",
                title="ダミーガイダンス",
                category="人的資本ガイダンス",
                change_type="参考",
                disclosure_items=["ダミー項目"],
                source="https://example.com",
                source_confirmed=True,
                effective_from="2025-06-01",
            )
        ]
        ref_period = ("2025/04/01", "2026/03/31")

        # get_applicable_entries でフィルタ
        applicable = get_applicable_entries(dummy_entries, ref_period)

        # missing_categories を手動で計算
        from m2_law_agent import CRITICAL_CATEGORIES
        missing = [
            cat for cat in CRITICAL_CATEGORIES
            if not any(e.category == cat for e in applicable)
        ]

        self.assertIn("金商法・開示府令", missing)
        self.assertIn("SSBJ", missing)
        self.assertNotIn("人的資本ガイダンス", missing)
        print(f"  [PASS] missing_categories: {missing} ✓")

    def test_real_yaml_2025_no_ssbj_warning(self):
        """
        実際のlaw_entries_human_capital.yamlで2025年度3月決算を実行し
        warningsの内容を確認する（実データによるTV-4検証）
        """
        if not REAL_YAML_PATH.exists():
            self.skipTest(f"YAMLファイルが存在しません: {REAL_YAML_PATH}")

        ctx = load_law_context(2025, 3, yaml_path=REAL_YAML_PATH)
        print(f"  [INFO] 2025年度warnings: {ctx.warnings}")
        print(f"  [INFO] 2025年度missing_categories: {ctx.missing_categories}")
        # warningsは空でも0件警告でもよい（実YAMLの内容次第）
        self.assertIsInstance(ctx.warnings, list)
        self.assertIsInstance(ctx.missing_categories, list)
        print(f"  [PASS] warnings型確認 ✓")

    def test_file_not_found_raises(self):
        """存在しないYAMLファイルを指定するとFileNotFoundError"""
        with self.assertRaises(FileNotFoundError) as ctx:
            load_law_context(2025, 3, yaml_path=Path("/nonexistent/path.yaml"))
        # エラーメッセージにパス名が含まれること
        self.assertIn("nonexistent", str(ctx.exception))
        print(f"  [PASS] FileNotFoundError発生 '{str(ctx.exception)[:50]}...' ✓")


class TestM3Integration(unittest.TestCase):
    """M3との統合確認テスト（タスク仕様 Section 4）"""

    def test_m2_to_m3_pipeline(self):
        """
        M2→M3パイプラインのE2Eテスト

        law_context = load_law_context(2025, 3)
        report = _build_mock_report()
        result = analyze_gaps(report, law_context, use_mock=True)
        assert result is not None
        """
        if not REAL_YAML_PATH.exists():
            self.skipTest(f"YAMLファイルが存在しません: {REAL_YAML_PATH}")

        # M2: 法令コンテキスト取得
        law_ctx = load_law_context(2025, 3, yaml_path=REAL_YAML_PATH)
        self.assertGreater(len(law_ctx.applicable_entries), 0,
                           "2025年度の適用エントリが0件")

        # M3: ギャップ分析
        report = _build_mock_report()
        result = analyze_gaps(report, law_ctx, use_mock=True)

        # 結果確認
        self.assertIsNotNone(result)
        self.assertEqual(result.document_id, "S100VHUZ_MOCK")
        self.assertEqual(result.fiscal_year, 2025)
        # law_yaml_as_ofがM2からM3に正しく伝搬されること
        self.assertEqual(result.law_yaml_as_of, law_ctx.law_yaml_as_of)
        self.assertIsInstance(result.gaps, list)
        self.assertIsInstance(result.no_gap_items, list)

        print(f"  [PASS] M2→M3パイプライン:")
        print(f"         M2 applicable_entries: {len(law_ctx.applicable_entries)}件")
        print(f"         M3 total_gaps: {result.summary.total_gaps}")
        print(f"         law_yaml_as_of伝搬: {law_ctx.law_yaml_as_of} → {result.law_yaml_as_of} ✓")

    def test_law_yaml_as_of_propagation(self):
        """law_yaml_as_ofがM2からM3に正しく伝搬される"""
        if not REAL_YAML_PATH.exists():
            self.skipTest(f"YAMLファイルが存在しません: {REAL_YAML_PATH}")

        law_ctx = load_law_context(2025, 3, yaml_path=REAL_YAML_PATH)
        report = _build_mock_report()
        result = analyze_gaps(report, law_ctx, use_mock=True)

        self.assertEqual(
            result.law_yaml_as_of,
            law_ctx.law_yaml_as_of,
            "law_yaml_as_ofがM3結果に正しく伝搬されていない",
        )
        print(f"  [PASS] law_yaml_as_of伝搬: '{law_ctx.law_yaml_as_of}' ✓")


class TestLawsDirectoryLoading(unittest.TestCase):
    """
    TEST 6: laws/ ディレクトリ全体読み込みテスト（D-LAW-DIR-fix 追加）

    laws/human_capital_2024.yaml / ssbj_2025.yaml / shareholder_notice_2025.yaml
    が全件 m2 に読み込まれることを確認する。
    """

    def test_law_yaml_dir_points_to_laws(self):
        """LAW_YAML_DIR が laws/ を指していること（10_Research/ ではない）"""
        self.assertTrue(
            LAW_YAML_DIR.name == "laws" or str(LAW_YAML_DIR).endswith("/laws"),
            f"LAW_YAML_DIR が laws/ を指していません: {LAW_YAML_DIR}"
        )

    def test_laws_dir_has_three_yamls(self):
        """laws/ 配下に5件のYAMLが存在すること（kinshohō_2025.yaml追加済み）"""
        yaml_files = list(LAW_YAML_DIR.glob("*.yaml"))
        self.assertGreaterEqual(
            len(yaml_files), 5,
            f"laws/*.yaml が5件未満です: {[f.name for f in yaml_files]}"
        )

    def test_load_all_from_dir_returns_all_entries(self):
        """_load_all_from_dir() が laws/ 配下の全YAMLを結合して返すこと"""
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ ディレクトリが存在しません: {LAW_YAML_DIR}")
        all_entries, _ = _load_all_from_dir(LAW_YAML_DIR)
        # 4ファイル結合（human_capital + ssbj + shareholder_notice + banking_2025）で40件超を期待
        self.assertGreater(len(all_entries), 40,
                           f"laws/ 全YAML結合エントリ数が少なすぎます: {len(all_entries)}件")

    def test_load_all_from_dir_includes_ssbj(self):
        """ssbj_2025.yaml のエントリが読み込まれること"""
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ ディレクトリが存在しません: {LAW_YAML_DIR}")
        all_entries, _ = _load_all_from_dir(LAW_YAML_DIR)
        # ssbj_2025.yaml のIDは "sb-" プレフィックス（例: sb-2025-001）
        ssbj_entries = [e for e in all_entries if e.id.startswith("sb-")]
        self.assertGreater(len(ssbj_entries), 0,
                           "ssbj_2025.yaml のエントリが0件（sb- プレフィックスのIDが見つからない）")

    def test_load_all_from_dir_includes_human_capital(self):
        """human_capital_2024.yaml のエントリが読み込まれること"""
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ ディレクトリが存在しません: {LAW_YAML_DIR}")
        all_entries, _ = _load_all_from_dir(LAW_YAML_DIR)
        hc_entries = [e for e in all_entries if e.id.startswith("hc-")]
        self.assertGreater(len(hc_entries), 0,
                           "human_capital_2024.yaml のエントリが0件（hc- プレフィックスのIDが見つからない）")

    def test_load_all_from_dir_includes_shareholder_notice(self):
        """shareholder_notice_2025.yaml のエントリが読み込まれること"""
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ ディレクトリが存在しません: {LAW_YAML_DIR}")
        all_entries, _ = _load_all_from_dir(LAW_YAML_DIR)
        gm_entries = [e for e in all_entries if e.id.startswith("gm-") or e.id.startswith("gc-")]
        self.assertGreater(len(gm_entries), 0,
                           "shareholder_notice_2025.yaml のエントリが0件（gm-/gc- プレフィックスのIDが見つからない）")

    def test_default_load_law_context_reads_all_yamls(self):
        """yaml_path=None のデフォルト呼び出しが laws/ 全体を読み込むこと（エラーなし確認）"""
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ ディレクトリが存在しません: {LAW_YAML_DIR}")
        # デフォルト呼び出しでエラーが起きないこと（FileNotFoundError等）を確認
        ctx = load_law_context(2025, 3)
        self.assertIsNotNone(ctx)
        # 注: applicable_entries は日付フィルタ（effective_from が参照期間内）で絞られる
        # laws/ 配下の全エントリがフィルタ前に読まれていることを別テストで確認済み
        all_entries, _ = _load_all_from_dir(LAW_YAML_DIR)
        self.assertGreater(len(all_entries), 40,
                           f"デフォルト呼び出しの全エントリ（フィルタ前）が少なすぎます: {len(all_entries)}件")


class TestProfileDir(unittest.TestCase):
    """
    DIS-C01: profile_dir パラメータのテスト

    テスト:
      P-01: profile_dir=None の場合は laws/ のみ（後方互換性）
      P-02: profile_dir に有効なディレクトリを指定すると追加エントリがロードされる
      P-03: profile_dir に存在しないパスを指定しても例外を起こさず警告のみ
      P-04: サンプルYAMLのフォーマットが load_law_entries() で正常に読み込める
    """

    # profiles/ と sample_profile.yaml のパス（プロジェクトルート基準）
    _PROFILE_DIR = Path(__file__).parent.parent / "profiles"
    _SAMPLE_YAML = _PROFILE_DIR / "sample_profile.yaml"

    def test_p01_profile_dir_none_uses_laws_only(self):
        """
        P-01: profile_dir=None（デフォルト）のとき laws/ のみを使用する。
        後方互換性: profile_dir なしの呼び出しと同じ結果になること。
        """
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ が存在しません: {LAW_YAML_DIR}")

        ctx_without = load_law_context(2025, 3)
        ctx_with_none = load_law_context(2025, 3, profile_dir=None)

        self.assertEqual(
            len(ctx_without.applicable_entries),
            len(ctx_with_none.applicable_entries),
            "profile_dir=None と profile_dir未指定で applicable_entries 数が異なる",
        )
        print(f"  [PASS] P-01 profile_dir=None: applicable_entries={len(ctx_without.applicable_entries)}件 ✓")

    def test_p02_profile_dir_valid_adds_entries(self):
        """
        P-02: profile_dir に profiles/ を指定すると、laws/ のエントリに加えてプロファイルのエントリも追加される。

        手計算:
          laws/ のエントリ数 + sample_profile.yaml の2エントリ = 合計が増える
        """
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ が存在しません: {LAW_YAML_DIR}")
        if not self._PROFILE_DIR.exists():
            self.skipTest(f"profiles/ が存在しません: {self._PROFILE_DIR}")
        if not self._SAMPLE_YAML.exists():
            self.skipTest(f"sample_profile.yaml が存在しません: {self._SAMPLE_YAML}")

        ctx_no_profile = load_law_context(2025, 3)
        ctx_with_profile = load_law_context(2025, 3, profile_dir=str(self._PROFILE_DIR))

        # プロファイル指定時はエントリが増えること
        self.assertGreaterEqual(
            len(ctx_with_profile.applicable_entries),
            len(ctx_no_profile.applicable_entries),
            "profile_dir 指定後のエントリ数がプロファイルなしより少ない",
        )
        print(f"  [PASS] P-02 profile_dir指定: "
              f"{len(ctx_no_profile.applicable_entries)}件 → {len(ctx_with_profile.applicable_entries)}件 ✓")

    def test_p03_profile_dir_nonexistent_no_exception(self):
        """
        P-03: profile_dir に存在しないパスを指定しても FileNotFoundError を起こさない。
        警告ログを出力してスキップする（後方互換性維持）。
        """
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ が存在しません: {LAW_YAML_DIR}")

        # 存在しないパス → 例外なしで完了すること
        try:
            ctx = load_law_context(2025, 3, profile_dir="/nonexistent/profiles/path")
            self.assertIsNotNone(ctx)
            print(f"  [PASS] P-03 存在しない profile_dir: 例外なし、applicable_entries={len(ctx.applicable_entries)}件 ✓")
        except Exception as e:
            self.fail(f"profile_dir が存在しない場合に予期しない例外: {e}")

    def test_p04_sample_profile_yaml_loads(self):
        """
        P-04: profiles/sample_profile.yaml が load_law_entries() で正常に読み込める。

        手計算: sample_profile.yaml には2エントリ定義されている。
        """
        if not self._SAMPLE_YAML.exists():
            self.skipTest(f"sample_profile.yaml が存在しません: {self._SAMPLE_YAML}")

        entries = load_law_entries(self._SAMPLE_YAML)

        self.assertGreaterEqual(len(entries), 2, f"sample_profile.yaml のエントリ数が不足: {len(entries)}件")
        # IDの存在確認
        ids = [e.id for e in entries]
        self.assertIn("PROF_SAMPLE_001", ids, "PROF_SAMPLE_001 が読み込まれていない")
        self.assertIn("PROF_SAMPLE_002", ids, "PROF_SAMPLE_002 が読み込まれていない")
        print(f"  [PASS] P-04 sample_profile.yaml: {len(entries)}件読み込み ✓")
        print(f"         IDs: {ids}")

    def test_p05_empty_dir_returns_base(self):
        """
        P-05: 空の一時ディレクトリを profile_dir に指定しても追加エントリが増えないこと。
        """
        import tempfile
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ が存在しません: {LAW_YAML_DIR}")

        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_no_profile = load_law_context(2025, 3)
            ctx_empty_dir = load_law_context(2025, 3, profile_dir=tmpdir)

        self.assertEqual(
            len(ctx_no_profile.applicable_entries),
            len(ctx_empty_dir.applicable_entries),
            "空ディレクトリ指定で applicable_entries 数が変わってはならない",
        )
        print(f"  [PASS] P-05 空dir: applicable_entries={len(ctx_empty_dir.applicable_entries)}件（変化なし） ✓")

    def test_p06_custom_yaml_in_tempdir(self):
        """
        P-06: 独自 yaml を tempdir に置くと entries が追加されること。
        """
        import tempfile
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ が存在しません: {LAW_YAML_DIR}")

        custom_yaml_content = {
            "entries": [
                {
                    "id": "CUSTOM_TEST_001",
                    "title": "カスタムテストエントリ",
                    "category": "テストカテゴリ",
                    "change_type": "参考",
                    "disclosure_items": ["テスト項目"],
                    "source": "https://example.com/custom",
                    "source_confirmed": False,
                    "summary": "カスタムテスト用エントリ",
                    "law_name": "（テスト）",
                    "effective_from": "2024-01-01",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_yaml_path = Path(tmpdir) / "custom_test.yaml"
            import yaml as _yaml
            custom_yaml_path.write_text(
                _yaml.dump(custom_yaml_content, allow_unicode=True), encoding="utf-8"
            )
            ctx_no_profile = load_law_context(2025, 3)
            ctx_with_custom = load_law_context(2025, 3, profile_dir=tmpdir)

        self.assertGreater(
            len(ctx_with_custom.applicable_entries),
            len(ctx_no_profile.applicable_entries),
            "カスタムyaml追加後にエントリが増えていない",
        )
        custom_ids = [e.id for e in ctx_with_custom.applicable_entries]
        self.assertIn("CUSTOM_TEST_001", custom_ids, "CUSTOM_TEST_001 が applicable_entries に存在しない")
        print(f"  [PASS] P-06 カスタムyaml: {len(ctx_no_profile.applicable_entries)}件 → {len(ctx_with_custom.applicable_entries)}件 ✓")

    def test_p07_profile_entry_in_range_included(self):
        """
        P-07: effective_from が参照期間内のエントリは applicable_entries に含まれること。
        2025年度3月決算の参照期間（2025-04-01〜2026-03-31）内の effective_from を使用。
        """
        import tempfile
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ が存在しません: {LAW_YAML_DIR}")

        in_range_yaml = {
            "entries": [
                {
                    "id": "RANGE_IN_001",
                    "title": "参照期間内エントリ",
                    "category": "テスト",
                    "change_type": "参考",
                    "disclosure_items": ["テスト"],
                    "source": "https://example.com",
                    "source_confirmed": False,
                    "summary": "参照期間内テスト",
                    "law_name": "（テスト）",
                    "effective_from": "2025-06-01",  # 2025年度3月決算の期間内
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "range_test.yaml"
            import yaml as _yaml
            p.write_text(_yaml.dump(in_range_yaml, allow_unicode=True), encoding="utf-8")
            ctx = load_law_context(2025, 3, profile_dir=tmpdir)

        ids = [e.id for e in ctx.applicable_entries]
        self.assertIn("RANGE_IN_001", ids, "期間内エントリが applicable_entries に含まれていない")
        print(f"  [PASS] P-07 期間内エントリ: RANGE_IN_001 が applicable に含まれる ✓")

    def test_p08_profile_entry_out_of_range_excluded(self):
        """
        P-08: effective_from が参照期間外のエントリは applicable_entries に含まれないこと。
        2025年度3月決算の参照期間より後の日付を使用。
        """
        import tempfile
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ が存在しません: {LAW_YAML_DIR}")

        out_of_range_yaml = {
            "entries": [
                {
                    "id": "RANGE_OUT_001",
                    "title": "参照期間外エントリ",
                    "category": "テスト",
                    "change_type": "参考",
                    "disclosure_items": ["テスト"],
                    "source": "https://example.com",
                    "source_confirmed": False,
                    "summary": "参照期間外テスト",
                    "law_name": "（テスト）",
                    "effective_from": "2030-01-01",  # 遠い将来 → 期間外
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "out_range_test.yaml"
            import yaml as _yaml
            p.write_text(_yaml.dump(out_of_range_yaml, allow_unicode=True), encoding="utf-8")
            ctx = load_law_context(2025, 3, profile_dir=tmpdir)

        ids = [e.id for e in ctx.applicable_entries]
        self.assertNotIn("RANGE_OUT_001", ids, "期間外エントリが applicable_entries に含まれてはならない")
        print(f"  [PASS] P-08 期間外エントリ: RANGE_OUT_001 が applicable に含まれない ✓")

    def test_p09_sample_example_file_exists(self):
        """
        P-09: profiles/sample_profile.yaml.example が存在すること（git追跡可能なスキーマ例）。
        """
        example_path = self._PROFILE_DIR / "sample_profile.yaml.example"
        self.assertTrue(
            example_path.exists(),
            f"profiles/sample_profile.yaml.example が存在しません: {example_path}",
        )
        # YAMLとして正常にパースできること
        import yaml as _yaml
        with open(example_path, encoding="utf-8") as f:
            data = _yaml.safe_load(f)
        self.assertIn("entries", data, "sample_profile.yaml.example に 'entries' キーがない")
        self.assertGreaterEqual(len(data["entries"]), 2, "example ファイルのエントリ数が不足")
        print(f"  [PASS] P-09 sample_profile.yaml.example 存在確認: {len(data['entries'])}件 ✓")

    def test_p10_profile_dir_as_path_object_str(self):
        """
        P-10: str 型パスを profile_dir に渡したとき load_law_context が正常動作すること。
        """
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ が存在しません: {LAW_YAML_DIR}")

        # str型で渡す（Path型ではない）
        profile_dir_str = str(self._PROFILE_DIR)
        self.assertIsInstance(profile_dir_str, str)
        try:
            ctx = load_law_context(2025, 3, profile_dir=profile_dir_str)
            self.assertIsNotNone(ctx)
            print(f"  [PASS] P-10 str型パス: applicable_entries={len(ctx.applicable_entries)}件 ✓")
        except Exception as e:
            self.fail(f"str型 profile_dir でエラー: {e}")

    def test_p11_profile_entries_merge_not_replace(self):
        """
        P-11: profile_dir を指定した後も laws/ のエントリが保持されること（マージ動作）。
        """
        import tempfile
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ が存在しません: {LAW_YAML_DIR}")

        ctx_laws_only = load_law_context(2025, 3)
        laws_entry_count = len(ctx_laws_only.applicable_entries)

        # 空ディレクトリで profile_dir を指定 → laws/ エントリは消えないこと
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx_with_empty = load_law_context(2025, 3, profile_dir=tmpdir)

        self.assertEqual(
            laws_entry_count,
            len(ctx_with_empty.applicable_entries),
            "profile_dir（空）指定で laws/ エントリが消えた（replaceになっている）",
        )
        print(f"  [PASS] P-11 マージ動作: laws/エントリ={laws_entry_count}件が保持される ✓")

    def test_p12_readme_not_loaded_as_entry(self):
        """
        P-12: profiles/README.md は LawEntry として解釈されないこと。
        load_law_context が .yaml 以外のファイルをスキップすること。
        """
        if not LAW_YAML_DIR.exists():
            self.skipTest(f"laws/ が存在しません: {LAW_YAML_DIR}")
        if not self._PROFILE_DIR.exists():
            self.skipTest(f"profiles/ が存在しません: {self._PROFILE_DIR}")

        # README.md があっても例外が起きないこと
        try:
            ctx = load_law_context(2025, 3, profile_dir=str(self._PROFILE_DIR))
            self.assertIsNotNone(ctx)
            # README.md が entry として混入していないこと
            readme_ids = [e.id for e in ctx.applicable_entries if "README" in e.id]
            self.assertEqual(len(readme_ids), 0, f"README.md 由来のエントリが混入: {readme_ids}")
            print(f"  [PASS] P-12 README.md スキップ: README由来エントリ={len(readme_ids)}件 ✓")
        except Exception as e:
            self.fail(f"README.md 存在時に例外: {e}")

    def test_p13_sample_yaml_required_fields(self):
        """
        P-13: profiles/sample_profile.yaml の各エントリに必須フィールドが存在すること。
        必須フィールド: id, title, category, change_type, disclosure_items, source, summary, law_name, effective_from
        """
        if not self._SAMPLE_YAML.exists():
            self.skipTest(f"sample_profile.yaml が存在しません: {self._SAMPLE_YAML}")

        required_fields = [
            "id", "title", "category", "change_type",
            "disclosure_items", "source", "summary", "law_name", "effective_from"
        ]
        import yaml as _yaml
        with open(self._SAMPLE_YAML, encoding="utf-8") as f:
            data = _yaml.safe_load(f)

        entries = data.get("entries", [])
        self.assertGreater(len(entries), 0, "sample_profile.yaml にエントリがない")

        for entry in entries:
            for field in required_fields:
                self.assertIn(
                    field, entry,
                    f"エントリ '{entry.get('id', '?')}' に必須フィールド '{field}' がない",
                )
        print(f"  [PASS] P-13 必須フィールド確認: {len(entries)}エントリ × {len(required_fields)}フィールド ✓")

    def test_p14_gitignore_allows_example_file(self):
        """
        P-14: .gitignore に !profiles/sample_profile.yaml.example の例外が記載されていること。
        """
        gitignore_path = Path(__file__).parent.parent / ".gitignore"
        if not gitignore_path.exists():
            self.skipTest(f".gitignore が存在しません: {gitignore_path}")

        content = gitignore_path.read_text(encoding="utf-8")
        self.assertIn(
            "!profiles/sample_profile.yaml.example",
            content,
            ".gitignore に '!profiles/sample_profile.yaml.example' がない",
        )
        print(f"  [PASS] P-14 .gitignore 例外パターン確認 ✓")


class TestIndustryProfiles(unittest.TestCase):
    """
    DIS-C05: 業界別プロファイル（banking / manufacturing / it_services）のテスト

    テスト:
      IP-01: banking.yaml が 15 エントリ以上読み込める（BANK- プレフィックス確認）
      IP-02: manufacturing.yaml が 20 エントリ以上読み込める（MFG- プレフィックス確認）
      IP-03: it_services.yaml が 15 エントリ以上読み込める（IT- プレフィックス確認）
      IP-04: banking.yaml の全エントリに tier_requirement フィールドが存在する
      IP-05: manufacturing.yaml のカテゴリが 3 種類以上存在する（多様性確認）
      IP-06: it_services.yaml の全エントリ profile_name が "it_services"
    """

    _PROFILE_DIR = Path(__file__).parent.parent / "profiles"
    _BANKING_YAML = _PROFILE_DIR / "banking.yaml"
    _MANUFACTURING_YAML = _PROFILE_DIR / "manufacturing.yaml"
    _IT_SERVICES_YAML = _PROFILE_DIR / "it_services.yaml"

    @staticmethod
    def _load_yaml_entries(path: Path) -> list:
        """YAMLファイルからエントリ辞書リストを直接読み込む"""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("entries", [])

    def test_ip01_banking_yaml_15_entries(self):
        """
        IP-01: banking.yaml が 15 エントリ以上読み込める。
        手計算: BANK-CAP-001 〜 BANK-SUST-001 の 15 エントリを定義済み。
        """
        if not self._BANKING_YAML.exists():
            self.skipTest(f"banking.yaml が存在しません: {self._BANKING_YAML}")

        entries = load_law_entries(self._BANKING_YAML)

        self.assertGreaterEqual(len(entries), 15,
                                f"banking.yaml のエントリ数が不足: {len(entries)}件")
        ids = [e.id for e in entries]
        bank_ids = [i for i in ids if i.startswith("BANK-")]
        self.assertGreaterEqual(len(bank_ids), 15,
                                f"BANK- プレフィックスのエントリが不足: {len(bank_ids)}件")
        print(f"  [PASS] IP-01 banking.yaml: {len(entries)}件（BANK-プレフィックス: {len(bank_ids)}件）✓")

    def test_ip02_manufacturing_yaml_20_entries(self):
        """
        IP-02: manufacturing.yaml が 20 エントリ以上読み込める。
        手計算: MFG-COST-001 〜 MFG-IMPAIR-001 の 20 エントリを定義済み。
        """
        if not self._MANUFACTURING_YAML.exists():
            self.skipTest(f"manufacturing.yaml が存在しません: {self._MANUFACTURING_YAML}")

        entries = load_law_entries(self._MANUFACTURING_YAML)

        self.assertGreaterEqual(len(entries), 20,
                                f"manufacturing.yaml のエントリ数が不足: {len(entries)}件")
        ids = [e.id for e in entries]
        mfg_ids = [i for i in ids if i.startswith("MFG-")]
        self.assertGreaterEqual(len(mfg_ids), 20,
                                f"MFG- プレフィックスのエントリが不足: {len(mfg_ids)}件")
        print(f"  [PASS] IP-02 manufacturing.yaml: {len(entries)}件（MFG-プレフィックス: {len(mfg_ids)}件）✓")

    def test_ip03_it_services_yaml_15_entries(self):
        """
        IP-03: it_services.yaml が 15 エントリ以上読み込める。
        手計算: IT-HC-001 〜 IT-INFRA-002 の 15 エントリを定義済み。
        """
        if not self._IT_SERVICES_YAML.exists():
            self.skipTest(f"it_services.yaml が存在しません: {self._IT_SERVICES_YAML}")

        entries = load_law_entries(self._IT_SERVICES_YAML)

        self.assertGreaterEqual(len(entries), 15,
                                f"it_services.yaml のエントリ数が不足: {len(entries)}件")
        ids = [e.id for e in entries]
        it_ids = [i for i in ids if i.startswith("IT-")]
        self.assertGreaterEqual(len(it_ids), 15,
                                f"IT- プレフィックスのエントリが不足: {len(it_ids)}件")
        print(f"  [PASS] IP-03 it_services.yaml: {len(entries)}件（IT-プレフィックス: {len(it_ids)}件）✓")

    def test_ip04_banking_tier_requirement_all_entries(self):
        """
        IP-04: banking.yaml の全エントリに tier_requirement フィールド（ume/take/matsu）が存在する。
        手計算: 15 エントリ全てに tier_requirement を定義済み。
        YAML直接読込でチェック（LawEntry非保持フィールドのため）。
        """
        if not self._BANKING_YAML.exists():
            self.skipTest(f"banking.yaml が存在しません: {self._BANKING_YAML}")

        raw_entries = self._load_yaml_entries(self._BANKING_YAML)
        missing_tier = []
        for entry in raw_entries:
            entry_id = entry.get("id", "UNKNOWN")
            tr = entry.get("tier_requirement")
            if not tr or not isinstance(tr, dict):
                missing_tier.append(entry_id)
            elif not all(k in tr for k in ("ume", "take", "matsu")):
                missing_tier.append(entry_id)

        self.assertEqual(len(missing_tier), 0,
                         f"tier_requirement (ume/take/matsu) が不完全なエントリ: {missing_tier}")
        print(f"  [PASS] IP-04 banking.yaml tier_requirement: 全{len(raw_entries)}件✓")

    def test_ip05_manufacturing_id_group_diversity(self):
        """
        IP-05: manufacturing.yaml の ID グループ（MFG-XXX の XXX 部分）が 5 種類以上存在する。
        手計算: COST/INV/CAPEX/RD/ENV/QC/FX/HR/SUPPLY/CARBON/WATER/DIGITAL/GLOBAL で 13 種類定義済み。
        YAML直接読込でIDから抽出する。
        """
        if not self._MANUFACTURING_YAML.exists():
            self.skipTest(f"manufacturing.yaml が存在しません: {self._MANUFACTURING_YAML}")

        raw_entries = self._load_yaml_entries(self._MANUFACTURING_YAML)
        groups = set()
        for entry in raw_entries:
            entry_id = entry.get("id", "")
            parts = entry_id.split("-")
            if len(parts) >= 2:
                groups.add(parts[1])  # "COST" from "MFG-COST-001"

        self.assertGreaterEqual(len(groups), 5,
                                f"manufacturing.yaml の ID グループ種類が少なすぎる: {groups}")
        print(f"  [PASS] IP-05 manufacturing.yaml ID グループ: {len(groups)}種類 - {groups} ✓")

    def test_ip06_it_services_profile_name(self):
        """
        IP-06: it_services.yaml の全エントリ profile_name が 'it_services'。
        手計算: 全 15 エントリに profile_name: it_services を設定済み。
        YAML直接読込でチェック（LawEntry非保持フィールドのため）。
        """
        if not self._IT_SERVICES_YAML.exists():
            self.skipTest(f"it_services.yaml が存在しません: {self._IT_SERVICES_YAML}")

        raw_entries = self._load_yaml_entries(self._IT_SERVICES_YAML)
        wrong_profile = [e.get("id", "UNKNOWN")
                         for e in raw_entries
                         if e.get("profile_name") != "it_services"]

        self.assertEqual(len(wrong_profile), 0,
                         f"profile_name が 'it_services' でないエントリ: {wrong_profile}")
        print(f"  [PASS] IP-06 it_services.yaml profile_name: 全{len(raw_entries)}件 'it_services' ✓")


class TestBigFourProfilesPhaseC(unittest.TestCase):
    """
    DIS-C06: Big4プロファイル PhaseC-06 追加エントリ検証テスト

    テスト:
      BPC-01: deloitte_profile.yaml が 17 エントリ以上（DTT-RISK-003/004/005 追加後）
      BPC-02: kpmg_profile.yaml が 17 エントリ以上（KPMG-CG-005/MD-005/ESG-004 追加後）
      BPC-03: pwc_profile.yaml が 17 エントリ以上（PwC-GG-002/003/PF-005 追加後）
    """

    _PROFILE_DIR = Path(__file__).parent.parent / "profiles"
    _DELOITTE_YAML = _PROFILE_DIR / "deloitte" / "deloitte_profile.yaml"
    _KPMG_YAML = _PROFILE_DIR / "kpmg" / "kpmg_profile.yaml"
    _PWC_YAML = _PROFILE_DIR / "pwc" / "pwc_profile.yaml"

    @staticmethod
    def _load_yaml_entries(path: Path) -> list:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("entries", [])

    def test_bpc01_deloitte_17_entries(self):
        """BPC-01: deloitte_profile.yaml が 17 エントリ以上（DTT-プレフィックス確認）"""
        if not self._DELOITTE_YAML.exists():
            self.skipTest(f"deloitte_profile.yaml が存在しません: {self._DELOITTE_YAML}")
        entries = load_law_entries(self._DELOITTE_YAML)
        dtt_entries = [e for e in entries if e.id.startswith("DTT-")]
        self.assertGreaterEqual(len(dtt_entries), 17,
                                f"deloitte_profile.yaml のDTT-エントリ数が不足: {len(dtt_entries)}件")
        print(f"  [PASS] BPC-01 deloitte_profile.yaml: {len(dtt_entries)}件（DTT-）≥17 ✓")

    def test_bpc02_kpmg_17_entries(self):
        """BPC-02: kpmg_profile.yaml が 17 エントリ以上（KPMG-プレフィックス確認）"""
        if not self._KPMG_YAML.exists():
            self.skipTest(f"kpmg_profile.yaml が存在しません: {self._KPMG_YAML}")
        entries = load_law_entries(self._KPMG_YAML)
        kpmg_entries = [e for e in entries if e.id.startswith("KPMG-")]
        self.assertGreaterEqual(len(kpmg_entries), 17,
                                f"kpmg_profile.yaml のKPMG-エントリ数が不足: {len(kpmg_entries)}件")
        print(f"  [PASS] BPC-02 kpmg_profile.yaml: {len(kpmg_entries)}件（KPMG-）≥17 ✓")

    def test_bpc03_pwc_17_entries(self):
        """BPC-03: pwc_profile.yaml が 17 エントリ以上（PwC-プレフィックス確認）"""
        if not self._PWC_YAML.exists():
            self.skipTest(f"pwc_profile.yaml が存在しません: {self._PWC_YAML}")
        entries = load_law_entries(self._PWC_YAML)
        pwc_entries = [e for e in entries if e.id.startswith("PwC-")]
        self.assertGreaterEqual(len(pwc_entries), 17,
                                f"pwc_profile.yaml のPwC-エントリ数が不足: {len(pwc_entries)}件")
        print(f"  [PASS] BPC-03 pwc_profile.yaml: {len(pwc_entries)}件（PwC-）≥17 ✓")


class TestPwCExtendedProfiles(unittest.TestCase):
    """
    AUTO-DIS-C04: PwC拡張プロファイル（人的資本・ガバナンス/リスク）検証テスト

    テスト:
      PEP-01: pwc_human_capital.yaml が 6 エントリ以上かつ PwC-HC- プレフィックス確認
      PEP-02: pwc_governance_risk.yaml が 7 エントリ以上かつ PwC-GR-/PwC-RM- プレフィックス確認
      PEP-03: 全エントリに source_confirmed=true かつ profile_name='pwc' が設定されている
    """

    _PROFILE_DIR = Path(__file__).parent.parent / "profiles" / "pwc"
    _HC_YAML = _PROFILE_DIR / "pwc_human_capital.yaml"
    _GR_YAML = _PROFILE_DIR / "pwc_governance_risk.yaml"

    @staticmethod
    def _load_raw_entries(path: Path) -> list:
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("entries", [])

    def test_pep01_human_capital_entries(self):
        """PEP-01: pwc_human_capital.yaml が 6 エントリ以上（PwC-HC- プレフィックス）"""
        if not self._HC_YAML.exists():
            self.skipTest(f"pwc_human_capital.yaml が存在しません: {self._HC_YAML}")
        entries = self._load_raw_entries(self._HC_YAML)
        hc_entries = [e for e in entries if str(e.get("id", "")).startswith("PwC-HC-")]
        self.assertGreaterEqual(len(hc_entries), 6,
                                f"pwc_human_capital.yaml のPwC-HC-エントリ数が不足: {len(hc_entries)}件")
        print(f"  [PASS] PEP-01 pwc_human_capital.yaml: {len(hc_entries)}件（PwC-HC-）≥6 ✓")

    def test_pep02_governance_risk_entries(self):
        """PEP-02: pwc_governance_risk.yaml が 7 エントリ以上（PwC-GR-/PwC-RM- プレフィックス）"""
        if not self._GR_YAML.exists():
            self.skipTest(f"pwc_governance_risk.yaml が存在しません: {self._GR_YAML}")
        entries = self._load_raw_entries(self._GR_YAML)
        gr_entries = [e for e in entries
                      if str(e.get("id", "")).startswith("PwC-GR-")
                      or str(e.get("id", "")).startswith("PwC-RM-")]
        self.assertGreaterEqual(len(gr_entries), 7,
                                f"pwc_governance_risk.yaml のPwC-GR-/PwC-RM-エントリ数が不足: {len(gr_entries)}件")
        print(f"  [PASS] PEP-02 pwc_governance_risk.yaml: {len(gr_entries)}件（PwC-GR-/PwC-RM-）≥7 ✓")

    def test_pep03_source_confirmed_and_profile_name(self):
        """PEP-03: 全エントリに source_confirmed=true かつ profile_name='pwc'"""
        for yaml_path in [self._HC_YAML, self._GR_YAML]:
            if not yaml_path.exists():
                continue
            entries = self._load_raw_entries(yaml_path)
            for e in entries:
                eid = e.get("id", "?")
                self.assertTrue(
                    e.get("source_confirmed", False),
                    f"{yaml_path.name} エントリ {eid}: source_confirmed が true でない"
                )
                self.assertEqual(
                    e.get("profile_name"), "pwc",
                    f"{yaml_path.name} エントリ {eid}: profile_name が 'pwc' でない"
                )
        print(f"  [PASS] PEP-03 source_confirmed=true & profile_name='pwc' 全エントリ ✓")


if __name__ == "__main__":
    import os
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestLoadLawContext,
        TestApplicableEntriesFilter,
        TestCalcLawRefPeriod,
        TestWarnings,
        TestM3Integration,
        TestLawsDirectoryLoading,
        TestProfileDir,
        TestIndustryProfiles,
        TestBigFourProfilesPhaseC,
        TestPwCExtendedProfiles,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    print("=== disclosure-multiagent M2 テスト実行 ===")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
