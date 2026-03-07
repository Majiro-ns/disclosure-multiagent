"""
test_generate_sample_pdf.py
============================
generate_sample_pdf.py のテスト。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# scripts/ をパスに追加（他のテストと同方式）
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from generate_sample_pdf import generate, OUTPUT_PATH, _find_jp_font


class TestFindJpFont:
    def test_returns_str_or_none(self):
        result = _find_jp_font()
        assert result is None or isinstance(result, str)

    def test_returned_path_exists_when_found(self):
        result = _find_jp_font()
        if result is not None:
            assert Path(result).exists()


class TestGenerate:
    def test_generates_pdf_at_default_path(self, tmp_path):
        out = generate(tmp_path / "sample.pdf")
        assert out.exists()
        assert out.suffix == ".pdf"

    def test_output_is_valid_pdf(self, tmp_path):
        out = generate(tmp_path / "sample.pdf")
        content = out.read_bytes()
        # PDFヘッダ確認
        assert content[:4] == b"%PDF"

    def test_pdf_is_not_empty(self, tmp_path):
        out = generate(tmp_path / "sample.pdf")
        # 最低 1KB 以上
        assert out.stat().st_size >= 1024

    def test_returns_path_object(self, tmp_path):
        out = generate(tmp_path / "sample.pdf")
        assert isinstance(out, Path)

    def test_creates_parent_dir(self, tmp_path):
        nested = tmp_path / "sub" / "dir" / "sample.pdf"
        out = generate(nested)
        assert out.exists()

    def test_default_output_path_constant(self):
        expected = PROJECT_ROOT / "tests" / "fixtures" / "sample_yuho.pdf"
        assert OUTPUT_PATH == expected


class TestSampleYuhoPdf:
    """tests/fixtures/sample_yuho.pdf が生成済みであることを確認。"""

    def test_fixture_exists(self):
        assert OUTPUT_PATH.exists(), f"{OUTPUT_PATH} が存在しません。generate_sample_pdf.py を実行してください。"

    def test_fixture_is_pdf(self):
        content = OUTPUT_PATH.read_bytes()
        assert content[:4] == b"%PDF"

    def test_fixture_size_reasonable(self):
        # 10KB 〜 10MB の範囲
        size = OUTPUT_PATH.stat().st_size
        assert 10_000 <= size <= 10_000_000, f"PDFサイズ異常: {size} bytes"
