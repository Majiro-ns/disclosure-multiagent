"""scripts/conftest.py

pytest が scripts/ 配下のテストを実行する際に scripts/ ディレクトリを
sys.path に追加する。

scripts/test_m*.py は `from m1_pdf_agent import ...` のように
scripts/ 相対でモジュールをインポートするため、
プロジェクトルートから pytest を実行する場合にモジュールが見つからない問題を解消する。

cmd_360k_a7c にて追加（2026-03-14）。
"""
import sys
from pathlib import Path

# scripts/ ディレクトリを sys.path の先頭に追加
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
