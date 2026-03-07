"""
run_pipeline.py — disclosure-check CLI entrypoint

pip install disclosure-multiagent でインストール後に
  disclosure-check your_yuho.pdf --company-name "株式会社A" --fiscal-year 2025 --level 竹
として呼び出せる。

実装は run_e2e.py の main() に委譲する。
"""

from scripts.run_e2e import main

__all__ = ["main"]
