"""
generate_sample_pdf.py
======================
架空企業「株式会社テスト商事」の有価証券報告書サンプルPDFを生成する。

用途:
  - disclosure-multiagent のOSS公開デモ用フィクスチャ
  - tests/fixtures/sample_yuho.pdf として配置
  - 梅レベル（60点・法令準拠ライン）の人的資本開示例を含む

実行方法:
  python3 scripts/generate_sample_pdf.py
  # → tests/fixtures/sample_yuho.pdf を生成

要件:
  pip install fpdf2

作成: Majiro-ns / cmd_349k_a4a
"""

from __future__ import annotations

import sys
from pathlib import Path

# プロジェクトルート（このスクリプトの1つ上のディレクトリ）
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_PATH = PROJECT_ROOT / "tests" / "fixtures" / "sample_yuho.pdf"

# 日本語フォント候補（優先順）
_JP_FONT_CANDIDATES = [
    "/mnt/c/Windows/Fonts/NotoSansJP-VF.ttf",
    "/mnt/c/Windows/Fonts/msgothic.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
]


def _find_jp_font() -> str | None:
    """利用可能な日本語フォントを探す。"""
    for path in _JP_FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def generate(output_path: Path = OUTPUT_PATH) -> Path:
    """架空企業サンプル有報PDFを生成して output_path に保存する。"""
    try:
        from fpdf import FPDF
    except ImportError:
        print("[ERROR] fpdf2 がインストールされていません。pip install fpdf2 を実行してください。")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # 日本語フォント設定
    jp_font = _find_jp_font()
    font_name = "NotoJP"
    if jp_font:
        try:
            pdf.add_font(font_name, "", jp_font)
            use_jp = True
        except Exception:
            use_jp = False
            font_name = "Helvetica"
    else:
        use_jp = False
        font_name = "Helvetica"

    def set_heading(size: int = 14) -> None:
        pdf.set_font(font_name, size=size)

    def set_body(size: int = 10) -> None:
        pdf.set_font(font_name, size=size)

    def add_heading(text: str, size: int = 14, ln_after: int = 6) -> None:
        set_heading(size)
        pdf.multi_cell(0, 8, text)
        pdf.ln(ln_after)

    def add_body(text: str, ln_after: int = 4) -> None:
        set_body(10)
        pdf.multi_cell(0, 6, text)
        pdf.ln(ln_after)

    # ─────────────────────────────────────────────────────────
    # 表紙
    # ─────────────────────────────────────────────────────────
    pdf.add_page()
    add_heading("【表紙】", size=16)
    add_body(
        "有価証券報告書\n"
        "\n"
        "事業年度　第25期（自 2024年4月1日 至 2025年3月31日）\n"
        "\n"
        "会社名　　株式会社テスト商事\n"
        "代表者名　代表取締役社長　山田 太郎\n"
        "本店所在地　東京都千代田区丸の内1-1-1\n"
        "提出日　　2025年6月27日\n"
        "提出先　　関東財務局長\n"
        "縦覧に供する場所　株式会社東京証券取引所（東京都中央区日本橋兜町2-1）\n"
    )

    # ─────────────────────────────────────────────────────────
    # 第一部 企業情報
    # ─────────────────────────────────────────────────────────
    pdf.add_page()
    add_heading("第一部 企業情報", size=15)

    # 1【企業の概況】
    add_heading("1【企業の概況】", size=13)
    add_body(
        "（1）主要な経営指標等の推移\n"
        "\n"
        "　当社は一般消費財の製造・販売を主たる事業とする株式会社です。\n"
        "\n"
        "　■ 経営指標（第25期）\n"
        "　売上高：50億円\n"
        "　営業利益：3億円（営業利益率6%）\n"
        "　経常利益：2億8千万円\n"
        "　純利益：1億9千万円\n"
        "　総資産：80億円\n"
        "　自己資本比率：45%\n"
        "\n"
        "（2）沿革\n"
        "　2000年4月　東京都千代田区にて設立\n"
        "　2010年3月　東京証券取引所プライム市場上場\n"
        "　2024年4月　現商号に変更\n"
    )

    # 2【事業の内容】
    add_heading("2【事業の内容】", size=13)
    add_body(
        "　当社グループは、消費財の製造・販売を中心に事業を展開しております。\n"
        "　主要製品：家庭用品、食品関連器具、オフィス用品\n"
        "　主な販売チャネル：量販店、ECサイト、代理店\n"
    )

    # ─────────────────────────────────────────────────────────
    # 第二部 企業の詳細情報（サステナビリティ・人的資本）
    # ─────────────────────────────────────────────────────────
    pdf.add_page()
    add_heading("第二部 企業の詳細情報", size=15)

    # サステナビリティ
    add_heading("2【サステナビリティに関する考え方及び取組】", size=13)
    add_body(
        "　当社は、持続可能な社会の実現に向け、ESG経営を推進しております。\n"
        "　特に人的資本への投資を経営の中核と位置づけ、以下の取り組みを実施しています。\n"
    )

    # 人的資本セクション（梅レベル）
    add_heading("（1）人的資本", size=12)
    add_body(
        "■ 基本方針\n"
        "　当社は「人材こそが最大の資産」と考え、従業員の能力開発と働きやすい職場環境の\n"
        "　整備に取り組んでいます。\n"
        "\n"
        "■ 人材育成方針\n"
        "　・新入社員研修：入社後3ヶ月間のOJT研修\n"
        "　・管理職研修：年1回のマネジメント研修（全管理職対象）\n"
        "　・外部研修支援：年間1人あたり10万円の自己啓発支援制度\n"
        "\n"
        "■ 人材の多様性（ダイバーシティ）\n"
        "　当社は、性別・年齢・国籍に関わらず、多様な人材が活躍できる環境づくりを推進します。\n"
        "\n"
        "■ 女性活躍推進\n"
        "　女性管理職比率：15%（2025年3月31日現在）\n"
        "　目標：2030年度までに20%以上\n"
        "\n"
        "■ 育児・介護支援\n"
        "　男性育児休業取得率：30%（2024年度実績）\n"
        "　育児休業取得後の復職率：95%（女性）、100%（男性）\n"
        "\n"
        "■ 従業員エンゲージメント\n"
        "　年1回の従業員満足度調査を実施しております（回答率：82%）。\n"
        "　なお、エンゲージメントスコアの開示については、次期以降に検討いたします。\n"
    )

    # 従業員の状況
    pdf.add_page()
    add_heading("3【従業員の状況】", size=13)
    add_body(
        "（1）提出会社の状況\n"
        "　（2025年3月31日現在）\n"
        "\n"
        "　従業員数：500名\n"
        "　平均年齢：38.5歳\n"
        "　平均勤続年数：12.3年\n"
        "　平均年間給与：650万円\n"
        "\n"
        "　■ 性別・雇用形態別内訳\n"
        "　　正規雇用：420名（男性260名・女性160名）\n"
        "　　非正規雇用：80名（男性30名・女性50名）\n"
        "\n"
        "（2）労働安全衛生\n"
        "　労働災害発生件数：2件（2024年度）\n"
        "　休業災害度数率：0.8（業種平均：1.2）\n"
        "\n"
        "（3）人材確保・育成に関する指標\n"
        "\n"
        "　■ 採用実績（2024年度）\n"
        "　　新卒採用：30名　中途採用：15名\n"
        "\n"
        "　■ 研修実績\n"
        "　　年間研修時間（1人あたり）：20時間\n"
        "　　管理職研修受講率：100%\n"
        "\n"
        "（注）当社は有価証券報告書の人的資本開示について、法令に定める事項を記載しております。\n"
        "　　開示内容の充実については継続的に検討してまいります。\n"
    )

    # ─────────────────────────────────────────────────────────
    # 第三部 財務情報
    # ─────────────────────────────────────────────────────────
    pdf.add_page()
    add_heading("第三部 財務情報", size=15)
    add_heading("1【財務諸表等】", size=13)
    add_body(
        "（1）貸借対照表（要約）\n"
        "　（単位：百万円）\n"
        "\n"
        "　流動資産：3,200\n"
        "　固定資産：4,800\n"
        "　資産合計：8,000\n"
        "\n"
        "　流動負債：2,100\n"
        "　固定負債：2,300\n"
        "　純資産：3,600\n"
        "　負債・純資産合計：8,000\n"
        "\n"
        "（2）損益計算書（要約）\n"
        "　（単位：百万円）\n"
        "\n"
        "　売上高：5,000\n"
        "　売上原価：3,200\n"
        "　売上総利益：1,800\n"
        "　販売費及び一般管理費：1,500\n"
        "　営業利益：300\n"
        "　経常利益：280\n"
        "　当期純利益：190\n"
        "\n"
        "（注）本財務諸表はデモ用の架空データです。実在の企業とは一切関係ありません。\n"
    )

    # フッター的な注記
    add_heading("【OSS利用上の注記】", size=11)
    add_body(
        "　このPDFは disclosure-multiagent（https://github.com/Majiro-ns/disclosure-multiagent）の\n"
        "　動作確認用に作成した架空企業サンプルです。\n"
        "　実在の企業・団体とは一切関係ありません。\n"
        "　USE_MOCK_LLM=true でAPIキー不要で実行できます。\n"
    )

    pdf.output(str(output_path))
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="架空企業サンプル有報PDF生成")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"出力先PDFパス（デフォルト: {OUTPUT_PATH}）",
    )
    args = parser.parse_args()

    out = generate(args.output)
    size_kb = out.stat().st_size // 1024
    print(f"[OK] 生成完了: {out} ({size_kb} KB)")
    print(f"     日本語フォント: {_find_jp_font() or '(なし - Helvetica使用)'}")
