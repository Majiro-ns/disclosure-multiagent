"""
test_big4_enhanced_profiles.py
==============================
disclosure-multiagent PhaseC-02/03: Big4強化プロファイル（EY/PwC）テスト

実行方法:
    cd scripts/
    python3 test_big4_enhanced_profiles.py

テスト一覧:
    TEST 01: ey_enhanced.yaml が存在しロード可能
    TEST 02: ey_enhanced.yaml が20エントリ以上含む
    TEST 03: ey_enhanced.yaml の全エントリが tier_requirement を持つ
    TEST 04: ey_enhanced.yaml の全エントリが必須フィールドを持つ
    TEST 05: ey_enhanced.yaml の profile_name が "ey_enhanced" である
    TEST 06: pwc_enhanced.yaml が存在しロード可能
    TEST 07: pwc_enhanced.yaml が20エントリ以上含む
    TEST 08: pwc_enhanced.yaml の全エントリが tier_requirement を持つ
    TEST 09: pwc_enhanced.yaml の全エントリが必須フィールドを持つ
    TEST 10: pwc_enhanced.yaml の profile_name が "pwc_enhanced" である
    TEST 11: ey_enhanced.yaml の tier_requirement 値が正当な値のみ
    TEST 12: pwc_enhanced.yaml の tier_requirement 値が正当な値のみ
    TEST 13: ey_enhanced.yaml のドメイン分散（複数カテゴリ）
    TEST 14: pwc_enhanced.yaml のドメイン分散（複数カテゴリ）
    TEST 15: m2_law_agent.load_law_entries() で ey_enhanced.yaml が読み込めること
    TEST 16: m2_law_agent.load_law_entries() で pwc_enhanced.yaml が読み込めること
    TEST 17: EYエントリの ID プレフィックス整合性（EYE- or EY-）
    TEST 18: PwCエントリの ID プレフィックス整合性（PWC-）
    TEST 19: ey_enhanced.yaml の全エントリが disclosure_items を持つ
    TEST 20: pwc_enhanced.yaml の全エントリが disclosure_items を持つ
"""

import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

PROFILES_DIR = Path(__file__).parent.parent / "profiles"
EY_ENHANCED_PATH = PROFILES_DIR / "ey_enhanced.yaml"
PWC_ENHANCED_PATH = PROFILES_DIR / "pwc_enhanced.yaml"

VALID_TIER_VALUES = {"必須", "推奨", "任意", "対象外"}
TIER_KEYS = {"ume", "take", "matsu"}


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_entries(data: dict) -> list:
    return data.get("entries") or data.get("amendments") or []


class TestEyEnhancedProfileExists(unittest.TestCase):
    """TEST 01: ey_enhanced.yaml が存在しロード可能"""

    def test_ey_enhanced_file_exists(self):
        self.assertTrue(
            EY_ENHANCED_PATH.exists(),
            f"ey_enhanced.yaml が存在しません: {EY_ENHANCED_PATH}",
        )

    def test_ey_enhanced_is_valid_yaml(self):
        data = _load_yaml(EY_ENHANCED_PATH)
        self.assertIsInstance(data, dict)


class TestEyEnhancedEntryCount(unittest.TestCase):
    """TEST 02: ey_enhanced.yaml が20エントリ以上含む"""

    def test_ey_enhanced_has_20_or_more_entries(self):
        data = _load_yaml(EY_ENHANCED_PATH)
        entries = _get_entries(data)
        self.assertGreaterEqual(
            len(entries),
            20,
            f"ey_enhanced.yaml のエントリ数が不足: {len(entries)} < 20",
        )


class TestEyEnhancedTierRequirement(unittest.TestCase):
    """TEST 03: ey_enhanced.yaml の全エントリが tier_requirement を持つ"""

    def test_all_entries_have_tier_requirement(self):
        data = _load_yaml(EY_ENHANCED_PATH)
        entries = _get_entries(data)
        for entry in entries:
            entry_id = entry.get("id", "UNKNOWN")
            self.assertIn(
                "tier_requirement",
                entry,
                f"tier_requirement なし: {entry_id}",
            )
            tr = entry["tier_requirement"]
            self.assertIsInstance(tr, dict, f"tier_requirement は dict 必須: {entry_id}")
            for key in TIER_KEYS:
                self.assertIn(key, tr, f"tier_requirement に '{key}' なし: {entry_id}")


class TestEyEnhancedRequiredFields(unittest.TestCase):
    """TEST 04: ey_enhanced.yaml の全エントリが必須フィールドを持つ"""

    REQUIRED_FIELDS = ["id", "title", "category", "disclosure_items", "source", "summary"]

    def test_all_entries_have_required_fields(self):
        data = _load_yaml(EY_ENHANCED_PATH)
        entries = _get_entries(data)
        for entry in entries:
            entry_id = entry.get("id", "UNKNOWN")
            for field in self.REQUIRED_FIELDS:
                self.assertIn(field, entry, f"必須フィールド '{field}' なし: {entry_id}")
                self.assertTrue(entry[field], f"フィールド '{field}' が空: {entry_id}")


class TestEyEnhancedProfileName(unittest.TestCase):
    """TEST 05: ey_enhanced.yaml の profile_name が "ey_enhanced" である"""

    def test_profile_name_is_ey_enhanced(self):
        data = _load_yaml(EY_ENHANCED_PATH)
        # トップレベルの profile_name
        self.assertEqual(data.get("profile_name"), "ey_enhanced")
        # 各エントリの profile_name
        entries = _get_entries(data)
        for entry in entries:
            entry_id = entry.get("id", "UNKNOWN")
            self.assertEqual(
                entry.get("profile_name"),
                "ey_enhanced",
                f"エントリの profile_name が不正: {entry_id}",
            )


class TestPwcEnhancedProfileExists(unittest.TestCase):
    """TEST 06: pwc_enhanced.yaml が存在しロード可能"""

    def test_pwc_enhanced_file_exists(self):
        self.assertTrue(
            PWC_ENHANCED_PATH.exists(),
            f"pwc_enhanced.yaml が存在しません: {PWC_ENHANCED_PATH}",
        )

    def test_pwc_enhanced_is_valid_yaml(self):
        data = _load_yaml(PWC_ENHANCED_PATH)
        self.assertIsInstance(data, dict)


class TestPwcEnhancedEntryCount(unittest.TestCase):
    """TEST 07: pwc_enhanced.yaml が20エントリ以上含む"""

    def test_pwc_enhanced_has_20_or_more_entries(self):
        data = _load_yaml(PWC_ENHANCED_PATH)
        entries = _get_entries(data)
        self.assertGreaterEqual(
            len(entries),
            20,
            f"pwc_enhanced.yaml のエントリ数が不足: {len(entries)} < 20",
        )


class TestPwcEnhancedTierRequirement(unittest.TestCase):
    """TEST 08: pwc_enhanced.yaml の全エントリが tier_requirement を持つ"""

    def test_all_entries_have_tier_requirement(self):
        data = _load_yaml(PWC_ENHANCED_PATH)
        entries = _get_entries(data)
        for entry in entries:
            entry_id = entry.get("id", "UNKNOWN")
            self.assertIn(
                "tier_requirement",
                entry,
                f"tier_requirement なし: {entry_id}",
            )
            tr = entry["tier_requirement"]
            self.assertIsInstance(tr, dict, f"tier_requirement は dict 必須: {entry_id}")
            for key in TIER_KEYS:
                self.assertIn(key, tr, f"tier_requirement に '{key}' なし: {entry_id}")


class TestPwcEnhancedRequiredFields(unittest.TestCase):
    """TEST 09: pwc_enhanced.yaml の全エントリが必須フィールドを持つ"""

    REQUIRED_FIELDS = ["id", "title", "category", "disclosure_items", "source", "summary"]

    def test_all_entries_have_required_fields(self):
        data = _load_yaml(PWC_ENHANCED_PATH)
        entries = _get_entries(data)
        for entry in entries:
            entry_id = entry.get("id", "UNKNOWN")
            for field in self.REQUIRED_FIELDS:
                self.assertIn(field, entry, f"必須フィールド '{field}' なし: {entry_id}")
                self.assertTrue(entry[field], f"フィールド '{field}' が空: {entry_id}")


class TestPwcEnhancedProfileName(unittest.TestCase):
    """TEST 10: pwc_enhanced.yaml の profile_name が "pwc_enhanced" である"""

    def test_profile_name_is_pwc_enhanced(self):
        data = _load_yaml(PWC_ENHANCED_PATH)
        self.assertEqual(data.get("profile_name"), "pwc_enhanced")
        entries = _get_entries(data)
        for entry in entries:
            entry_id = entry.get("id", "UNKNOWN")
            self.assertEqual(
                entry.get("profile_name"),
                "pwc_enhanced",
                f"エントリの profile_name が不正: {entry_id}",
            )


class TestEyEnhancedTierValues(unittest.TestCase):
    """TEST 11: ey_enhanced.yaml の tier_requirement 値が正当な値のみ"""

    def test_tier_values_are_valid(self):
        data = _load_yaml(EY_ENHANCED_PATH)
        entries = _get_entries(data)
        for entry in entries:
            entry_id = entry.get("id", "UNKNOWN")
            tr = entry.get("tier_requirement", {})
            for key in TIER_KEYS:
                val = tr.get(key, "")
                self.assertIn(
                    val,
                    VALID_TIER_VALUES,
                    f"不正な tier_requirement 値 [{key}]={val!r}: {entry_id}",
                )


class TestPwcEnhancedTierValues(unittest.TestCase):
    """TEST 12: pwc_enhanced.yaml の tier_requirement 値が正当な値のみ"""

    def test_tier_values_are_valid(self):
        data = _load_yaml(PWC_ENHANCED_PATH)
        entries = _get_entries(data)
        for entry in entries:
            entry_id = entry.get("id", "UNKNOWN")
            tr = entry.get("tier_requirement", {})
            for key in TIER_KEYS:
                val = tr.get(key, "")
                self.assertIn(
                    val,
                    VALID_TIER_VALUES,
                    f"不正な tier_requirement 値 [{key}]={val!r}: {entry_id}",
                )


class TestEyEnhancedDomainDiversity(unittest.TestCase):
    """TEST 13: ey_enhanced.yaml のドメイン分散（複数カテゴリ）"""

    def test_multiple_categories_present(self):
        data = _load_yaml(EY_ENHANCED_PATH)
        entries = _get_entries(data)
        categories = {e.get("category") for e in entries if e.get("category")}
        self.assertGreaterEqual(
            len(categories),
            3,
            f"カテゴリ数が不足（3以上必要）: {categories}",
        )


class TestPwcEnhancedDomainDiversity(unittest.TestCase):
    """TEST 14: pwc_enhanced.yaml のドメイン分散（複数カテゴリ）"""

    def test_multiple_categories_present(self):
        data = _load_yaml(PWC_ENHANCED_PATH)
        entries = _get_entries(data)
        categories = {e.get("category") for e in entries if e.get("category")}
        self.assertGreaterEqual(
            len(categories),
            3,
            f"カテゴリ数が不足（3以上必要）: {categories}",
        )


class TestLoadLawEntriesEy(unittest.TestCase):
    """TEST 15: m2_law_agent.load_law_entries() で ey_enhanced.yaml が読み込めること"""

    def test_load_via_m2_load_law_entries(self):
        try:
            from m2_law_agent import load_law_entries
        except ImportError:
            self.skipTest("m2_law_agent がインポートできません（scripts/ 配下で実行してください）")

        entries = load_law_entries(EY_ENHANCED_PATH)
        self.assertGreaterEqual(len(entries), 20)
        # 最初のエントリが LawEntry 型であることを確認
        first = entries[0]
        self.assertTrue(hasattr(first, "id"))
        self.assertTrue(hasattr(first, "title"))
        self.assertTrue(hasattr(first, "disclosure_items"))


class TestLoadLawEntriesPwc(unittest.TestCase):
    """TEST 16: m2_law_agent.load_law_entries() で pwc_enhanced.yaml が読み込めること"""

    def test_load_via_m2_load_law_entries(self):
        try:
            from m2_law_agent import load_law_entries
        except ImportError:
            self.skipTest("m2_law_agent がインポートできません（scripts/ 配下で実行してください）")

        entries = load_law_entries(PWC_ENHANCED_PATH)
        self.assertGreaterEqual(len(entries), 20)
        first = entries[0]
        self.assertTrue(hasattr(first, "id"))
        self.assertTrue(hasattr(first, "title"))
        self.assertTrue(hasattr(first, "disclosure_items"))


class TestEyEntryIdPrefix(unittest.TestCase):
    """TEST 17: EYエントリの ID プレフィックス整合性"""

    def test_all_ids_start_with_ey_prefix(self):
        data = _load_yaml(EY_ENHANCED_PATH)
        entries = _get_entries(data)
        for entry in entries:
            entry_id = entry.get("id", "")
            self.assertTrue(
                entry_id.startswith("EY"),
                f"EY プロファイルのIDが EY で始まっていない: {entry_id}",
            )


class TestPwcEntryIdPrefix(unittest.TestCase):
    """TEST 18: PwCエントリの ID プレフィックス整合性"""

    def test_all_ids_start_with_pwc_prefix(self):
        data = _load_yaml(PWC_ENHANCED_PATH)
        entries = _get_entries(data)
        for entry in entries:
            entry_id = entry.get("id", "")
            self.assertTrue(
                entry_id.startswith("PWC"),
                f"PwC プロファイルのIDが PWC で始まっていない: {entry_id}",
            )


class TestEyEnhancedDisclosureItems(unittest.TestCase):
    """TEST 19: ey_enhanced.yaml の全エントリが disclosure_items を持つ"""

    def test_all_entries_have_disclosure_items(self):
        data = _load_yaml(EY_ENHANCED_PATH)
        entries = _get_entries(data)
        for entry in entries:
            entry_id = entry.get("id", "UNKNOWN")
            items = entry.get("disclosure_items")
            self.assertTrue(
                items and len(items) >= 1,
                f"disclosure_items が空またはなし: {entry_id}",
            )


class TestPwcEnhancedDisclosureItems(unittest.TestCase):
    """TEST 20: pwc_enhanced.yaml の全エントリが disclosure_items を持つ"""

    def test_all_entries_have_disclosure_items(self):
        data = _load_yaml(PWC_ENHANCED_PATH)
        entries = _get_entries(data)
        for entry in entries:
            entry_id = entry.get("id", "UNKNOWN")
            items = entry.get("disclosure_items")
            self.assertTrue(
                items and len(items) >= 1,
                f"disclosure_items が空またはなし: {entry_id}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
