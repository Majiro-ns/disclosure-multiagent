---
title: "マルチエージェントで有報分析を並列化する — M1-M5パイプライン設計と実装"
emoji: "🏗️"
type: "tech"
topics: ["python", "ai", "multiagent", "有価証券報告書", "アーキテクチャ"]
published: false
---

# マルチエージェントで有報分析を並列化する — M1-M5パイプライン設計と実装

有価証券報告書（有報）は最大500ページにおよぶ複雑な文書だ。法令要件の照合、ギャップ特定、改善文案の生成を1つのスクリプトで実装しようとすると、責務が混在してテストが困難になり、改修コストが指数関数的に増加する。

この記事では、9エージェント構成（M1〜M9）のうち **コア5エージェント（M1〜M5）** の設計と実装を詳解する。各エージェントが単一責務を持ち、**独立してテスト可能**な設計がいかに並列処理と保守性を両立するかを示す。

:::message
**シリーズ構成**
- Phase1: **M1-M5コアパイプライン（本記事）**
- Phase2: M7 EDINET自動取得・M6法令照合・M8多年度比較
- Phase3: M9 Word/Excel出力・Streamlit UI・API化
:::

---

## 1. なぜマルチエージェントで並列化するのか

### 1.1 単体スクリプトの限界

有報チェックを単一の Python スクリプトで実装した場合の問題点を考えてみる。

```python
# ❌ 悪い設計: 全処理をmain()に詰め込む
def main(pdf_path, law_yaml_path, output_path):
    # 1. PDFからテキスト抽出（PyMuPDF）
    text = fitz.open(pdf_path)[0].get_text()

    # 2. 法令YAML読み込み（同一関数内）
    with open(law_yaml_path) as f:
        laws = yaml.safe_load(f)

    # 3. LLMでギャップ分析（APIコール）
    for law in laws:
        result = anthropic.messages.create(...)

    # 4. 提案文生成（LLMコール）
    proposals = generate_proposals(result)

    # 5. レポート出力
    ...
```

この設計の問題:
- **テストが困難**: PDFなしでは1行も動作確認できない
- **並列化不可**: M1（PDF解析）とM2（法令収集）は独立なのにシリアル実行になる
- **モック差し込み困難**: LLMのモック化にコード改修が必要
- **責務混在**: バグの原因特定に全コードを読む必要がある

### 1.2 マルチエージェント設計の原則

```
【単一責務の原則 + インターフェース契約】

M1（PDF解析） ─→ StructuredReport ─→ M3（ギャップ分析）
                                              ↑
M2（法令収集） ─→ LawContext ────────────────┘
                                              ↓
                              GapAnalysisResult ─→ M4（提案生成）
                                                          ↓
                                              list[ProposalSet] ─→ M5（レポート）
```

各エージェントは**データクラスをインターフェース**として持ち、他エージェントの内部実装に依存しない。M1がPDFをどう開くかをM3は知らなくていい。

---

## 2. 全体アーキテクチャ

### 2.1 M1-M5パイプライン概要

```
┌─────────────────────────────────────────────────────────────────┐
│                  Phase 1: コアパイプライン                          │
│                                                                   │
│  [PDFファイル]          [法令YAML群]                               │
│       │                    │                                       │
│       ▼                    ▼                                       │
│  ┌─────────┐        ┌─────────┐   ← 並列実行可能（M1/M2は独立）   │
│  │   M1    │        │   M2    │                                   │
│  │PDF解析  │        │法令収集  │                                   │
│  └────┬────┘        └────┬────┘                                   │
│       │ StructuredReport │ LawContext                              │
│       └────────┬─────────┘                                        │
│                ▼                                                   │
│          ┌─────────┐                                              │
│          │   M3    │  ← Claude Haiku（LLM）                       │
│          │ギャップ  │  ← 各セクション×各法令エントリで並列化可能   │
│          │ 分析    │                                               │
│          └────┬────┘                                              │
│               │ GapAnalysisResult                                 │
│               ▼                                                    │
│          ┌─────────┐                                              │
│          │   M4    │  ← Claude Haiku（LLM）                       │
│          │松竹梅提案│  ← 各GapItemで並列化可能                    │
│          └────┬────┘                                              │
│               │ list[ProposalSet]                                  │
│               ▼                                                    │
│          ┌─────────┐                                              │
│          │   M5    │  ← Markdown統合                              │
│          │レポート  │                                               │
│          └────┬────┘                                              │
│               │                                                    │
│               ▼                                                    │
│    [Markdownレポート.md]                                          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 ファイル構成

```
disclosure-multiagent/
├── scripts/
│   ├── m1_pdf_agent.py          # M1: PDF解析
│   ├── m2_law_agent.py          # M2: 法令収集
│   ├── m3_gap_analysis_agent.py # M3: ギャップ分析（全データクラス定義）
│   ├── m4_proposal_agent.py     # M4: 松竹梅提案生成
│   ├── m5_report_agent.py       # M5: レポート統合
│   └── app.py                   # Streamlit UI
├── laws/
│   ├── human_capital_2024.yaml  # 人的資本開示法令
│   ├── ssbj_2025.yaml           # SSBJ確定基準25件
│   └── shareholder_notice_2025.yaml  # 招集通知法令
└── tests/
    ├── test_m1_pdf_agent.py
    ├── test_m2_law_agent.py
    └── ...
```

### 2.3 M3が全データクラスを管理する設計

```python
# m3_gap_analysis_agent.py が「共通データクラス定義ファイル」を兼ねる
# M1, M2, M4, M5 はすべて m3 からインポートする

# m1_pdf_agent.py での使用例
from m3_gap_analysis_agent import (
    StructuredReport,
    SectionData,
    TableData,
)

# m2_law_agent.py での使用例
from m3_gap_analysis_agent import (
    LawContext,
    LawEntry,
    calc_law_ref_period,
    is_entry_applicable,
)
```

この設計は、M3を核に据えるという構造的判断だ。ギャップ分析が全データの交差点になるため、データクラス定義の場所として最も自然だ。

---

## 3. M1: PDF解析エージェント

### 3.1 役割と責務

M1は**PDFから構造化データへの変換**のみを担当する。LLMは使わない。

```python
def extract_report(
    pdf_path: str,
    fiscal_year: Optional[int] = None,
    fiscal_month_end: int = 3,
    company_name: str = "",
    extract_tables: bool = True,
    doc_type: str = "yuho",  # "yuho" | "shoshu"
) -> StructuredReport:
    """PDF → StructuredReport"""
```

### 3.2 セクション分割ロジック

有報の見出しパターンは規格化されている。`re.Pattern` のリストで対応する。

```python
HEADING_PATTERNS: list[re.Pattern] = [
    re.compile(r'^第[一二三四五六七八九十\d]+部'),        # 「第一部」「第2部」
    re.compile(r'^第[１２３４５６７８９\d]+【'),            # 「第１【企業の概況】」
    re.compile(r'^\d+【'),                                  # 「1【事業の概要】」
    re.compile(r'^【[^】]+】$'),                            # 「【表紙】」
    re.compile(r'^[（(]\d+[）)]\s*[\u4e00-\u9fff]'),        # 「（1）人的資本」
    re.compile(r'^\d+\.\s*[\u4e00-\u9fff]{2,}'),           # 「1. 人材戦略」
    re.compile(r'^[①②③④⑤⑥⑦⑧⑨⑩]'),                   # 丸数字
]
```

有報（`yuho`）と招集通知（`shoshu`）で別々のパターンを用意している。`doc_type` 引数1つで切り替え可能にすることで、**拡張性をコスト最小で実現**した。

### 3.3 テーブル抽出と処理時間のトレードオフ

```python
# PyMuPDF 1.23+ の find_tables() を使用
# extract_tables=False で処理時間を 11.5秒 → 0.5秒/社 に短縮（FINDING-001）
def extract_report(..., extract_tables: bool = True) -> StructuredReport:
    ...
    for page_num, page in enumerate(doc):
        text = page.get_text()
        page_texts.append(text)
        tables = _extract_tables_from_page(page) if extract_tables else []
```

テーブルを含む有報（財務指標の一覧）では `extract_tables=True` が重要だが、スループット優先のバッチ処理では `False` に切り替えることで **23倍の高速化**が可能だ。

### 3.4 PyMuPDF不要でテスト可能

```bash
# M1単体のモックテスト（PDFなし環境で実行）
python3 m1_pdf_agent.py --test
# → "セクション数: 3" "人的資本セクション: 2件" が出力される
```

```python
# テストコードでの使用例
def test_split_sections():
    mock_text = """第一部 企業情報
1【事業の概要】
当社の概要です。

2【サステナビリティに関する考え方及び取組】
人的資本の開示について記載します。"""

    sections = split_sections_from_text(mock_text)
    assert len(sections) == 2  # PDFなしで完全テスト可能
```

**M1のAPI（`split_sections_from_text`）はPDF非依存**なので、PyMuPDFがない CI環境でも全テストが通る。

---

## 4. M2: 法令収集エージェント

### 4.1 役割と責務

M2は**YAMLから適用法令の絞り込み**を担当する。LLMは使わない。

```python
def load_law_context(
    fiscal_year: int,
    fiscal_month_end: int = 3,
    yaml_path: Optional[Path] = None,
    categories: Optional[list[str]] = None,
) -> LawContext:
    """YAML → LawContext（適用法令一覧）"""
```

### 4.2 YAML設計: laws/ ディレクトリ

法令は3ファイルに分割管理している。

```yaml
# ssbj_2025.yaml の一部
amendments:
  - id: "sb-2025-008"
    title: "SSBJ確定基準 — 戦略：気候関連機会の特定と対応策"
    category: "SSBJ"
    change_type: "修正推奨"
    required_items:
      - "気候変動が事業機会に与える影響の特定・評価プロセス"
      - "特定された気候関連機会のリスト（中長期視点）"
    effective_from: "2025-03-01"
    target_companies: "大規模プライム（強制適用: 2027年3月期〜）"
```

ポイントは **`effective_from`（施行日）** の管理だ。有報は事業年度ごとに適用法令が変わる。M2は `calc_law_ref_period()` で参照期間を算出し、その期間に施行された法令のみを返す。

### 4.3 法令参照期間の算出

```python
def calc_law_ref_period(
    fiscal_year: int,
    fiscal_month_end: int = 3,
) -> tuple[str, str]:
    """
    有報の法令参照期間を算出する。

    例: fiscal_year=2025, fiscal_month_end=3
    → 参照期間: 2021/04/01 〜 2026/03/31（当期末まで）
    """
```

```python
# 実行例
ctx = load_law_context(fiscal_year=2025, fiscal_month_end=3)
print(f"適用エントリ: {len(ctx.applicable_entries)}件")
# → 適用エントリ: 12件 (2021年〜2026年3月の法令改正)
```

### 4.4 重要カテゴリの網羅性チェック

```python
CRITICAL_CATEGORIES = ["人的資本ガイダンス", "金商法・開示府令", "SSBJ"]

# 1件もエントリが取得できなかった場合に警告を発する
for cat in CRITICAL_CATEGORIES:
    if not any(e.category == cat for e in applicable):
        warnings.append(f"⚠️ 重要カテゴリのエントリが0件: {cat}")
```

法令YAMLの更新漏れや参照期間のミス設定を **自動検知**するセーフガードだ。

---

## 5. M3: ギャップ分析エージェント

### 5.1 役割と責務

M3は本システムの**中核エージェント**だ。M1の有報テキストとM2の法令リストを突き合わせ、LLMが記載の有無とギャップを判定する。

```python
def analyze_gaps(
    report: StructuredReport,
    law_ctx: LawContext,
) -> GapAnalysisResult:
    """有報 × 法令 → ギャップ分析結果"""
```

### 5.2 LLMへのプロンプト設計

```python
SYSTEM_PROMPT = """あなたは日本の有価証券報告書の開示コンプライアンス専門家です。

## 制約（必ず守ること）
1. 判定は「提供された法令開示項目の要件のみ」に基づいて行う。
   YAMLエントリとして提供されていない法令への言及は禁止する。
2. 有報テキストに明示的な記載がない場合は has_gap: true とする。
   「おそらく記載があるはず」という推測で has_gap: false としない。
3. 出力は必ず指定のJSONフォーマットで返す。フォーマット外の文章を追加しない。
4. 確信度（confidence）は "high"/"medium"/"low" のいずれか。"""
```

**ハルシネーション対策が重要**だ。制約を明示しないと、LLMは一般的なベストプラクティスに基づいて指摘を増やし、false positiveが増加する。

### 5.3 GapItem: 型安全なギャップ表現

```python
class ChangeType(str, Enum):
    """change_type の許容値"""
    ADD_MANDATORY = "追加必須"    # 法令で明示的に新設
    MODIFY_RECOMMENDED = "修正推奨"  # 内容の充実が求められる
    REFERENCE = "参考"              # 任意開示だが望ましい

@dataclass
class GapItem:
    gap_id: str
    section_id: str
    section_heading: str
    change_type: str          # ChangeType.value のいずれか
    has_gap: Optional[bool]
    disclosure_item: str      # 例: "気候関連機会のリスト"
    reference_law_id: str     # 例: "sb-2025-008"
    confidence: str           # "high" / "medium" / "low"

    def __post_init__(self) -> None:
        """change_type の enum バリデーション（hallucination対策）"""
        valid = {ct.value for ct in ChangeType}
        if self.change_type not in valid:
            raise ValueError(f"無効な change_type: {self.change_type}")
```

`__post_init__` でLLMが不正な change_type を生成した場合に即座に検知できる。

### 5.4 長文セクションのチャンク処理

```python
TEXT_CHUNK_MAX = 4000
TEXT_CHUNK_HEAD = 2000
TEXT_CHUNK_TAIL = 1000

def _build_user_prompt(section, disclosure_item, law_entry):
    text = section.text
    if len(text) > TEXT_CHUNK_MAX:
        # 先頭2000 + ... + 末尾1000（重要な結論が末尾に書かれやすい）
        text = text[:TEXT_CHUNK_HEAD] + "\n...[中略]...\n" + text[-TEXT_CHUNK_TAIL:]
```

有報の長文セクションをそのままLLMに渡すとコスト増大とコンテキスト超過が発生する。先頭と末尾を組み合わせるchunk戦略で **トークンコストを抑制**する。

### 5.5 関連セクションの絞り込み

全セクションに対してLLMを呼ぶのはコストの無駄だ。事前に `ALL_RELEVANCE_KEYWORDS` で関連セクションのみを抽出する。

```python
HUMAN_CAPITAL_KEYWORDS = [
    "人的資本", "人材", "従業員", "ダイバーシティ", "ESG", ...
]
SSBJ_KEYWORDS = [
    "SSBJ", "気候変動", "GHG", "Scope1", "移行計画", "物理リスク", ...
]
BANKING_KEYWORDS = [
    "バーゼル", "Basel", "自己資本比率", "CET1", "不良債権", ...
]
ALL_RELEVANCE_KEYWORDS = HUMAN_CAPITAL_KEYWORDS + SSBJ_KEYWORDS + BANKING_KEYWORDS
```

銀行・保険会社の有報には固有の開示項目（バーゼルIII対応等）があり、`BANKING_KEYWORDS` で業種特化の絞り込みを実現している。

---

## 6. M4: 松竹梅提案エージェント

### 6.1 役割と責務

M4はM3が検出したギャップ（不足開示項目）に対して、**3水準（松竹梅）の改善文案**を生成する。

```
梅（最小限対応）: 50〜120字  ← 最低限の法令対応
竹（スタンダード）: 100〜260字 ← 実務的な標準開示
松（充実開示）: 200〜480字   ← ベストプラクティス
```

企業は自社の開示方針・リソースに応じて選択できる。

### 6.2 Few-shot examples による品質安定化

```python
FEW_SHOT_EXAMPLES = {
    "企業戦略と関連付けた人材戦略": {
        "松": (
            "当社は、「2030年ビジョン」に掲げる事業成長率15%の達成に向け、"
            "事業戦略と連動した人材戦略を「人材ポートフォリオ計画」として策定しています。"
            "デジタル変革（DX）推進を担う専門人材を2028年度末までに現状比2倍（300名）に拡充する計画の下、"
            "採用・育成・リスキリングの三本柱で体制整備を進めています。..."
        ),
        "竹": "当社は事業戦略と人材戦略の連動を重視し...",
        "梅": "当社は事業成長に向けた人材育成計画を策定しています。",
    }
}
```

### 6.3 禁止パターンによる品質ゲート

LLMが生成した文案に法令条文の直接引用や根拠のない断言表現が含まれていないか自動チェックする。

```python
FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"第\d+条", "法令条文の直接引用（「第○○条」）"),
    (r"業界(?:トップ|No\.?1|一位)", "根拠のない業界比較"),
    (r"保証(?:いたし|し|する|します)", "保証表現"),
    (r"必ず(?!プレースホルダ)", "断言表現「必ず」"),
]

MAX_REGENERATE = 2  # 品質チェック失敗時の最大再生成回数
```

チェック失敗 → 再生成 → 最大2回。3回失敗でも `status="fail"` として結果を返す（停止しない）。

### 6.4 PlaceholderパターンによるXX置換促進

```python
PLACEHOLDER_PATTERN = re.compile(r'\[[^\]]{1,30}\]')
# 例: "[従業員数]%" "[2025年度計画値]" "[具体的な目標数値]"
```

企業固有の数値をハードコードさせず、`[XX]` 形式のプレースホルダとして残す。これにより、生成文案が**そのままコピペ可能なテンプレート**として機能する。

---

## 7. M5: レポート統合エージェント

### 7.1 役割と責務

M5はM1〜M4の全出力を受け取り、**完全なMarkdownレポート**を生成する。

```python
def generate_report(
    structured_report: StructuredReport,    # M1出力
    law_context: LawContext,                # M2出力
    gap_result: GapAnalysisResult,          # M3出力
    proposal_set: list[ProposalSet],        # M4出力
    level: str,                             # "松" / "竹" / "梅"
    year_diff: Optional[YearDiff] = None,   # M8出力（省略可）
) -> str:
    """全エージェント出力 → Markdownレポート"""
```

### 7.2 免責事項の動的生成

法令情報の取得日（`law_yaml_as_of`）をレポートに動的に埋め込む。

```python
def _build_disclaimer_detail(law_yaml_as_of: str) -> str:
    return (
        f"本レポートは、入力された有価証券報告書（公開済み）と"
        f"法令情報YAML（取得日: {law_yaml_as_of}）を基に自動生成されたものです。\n\n"
        "- 本システムは「参考情報の提供」を目的とし、開示内容の正確性を保証するものではありません"
    )
```

ハードコード禁止。`law_yaml_as_of` は `m2_law_agent.py` がYAMLファイルのコメントまたはmtimeから動的に取得する。

### 7.3 変更種別でソートされる出力

```python
CHANGE_TYPE_ORDER: dict[str, int] = {
    "追加必須": 0,   # 最優先
    "修正推奨": 1,
    "参考": 2,
}

sorted_gaps = sorted(gaps, key=lambda g: CHANGE_TYPE_ORDER.get(g.change_type, 9))
```

コンプライアンス担当者が**最も重要な指摘から確認できる**よう、追加必須 → 修正推奨 → 参考の順で自動ソートする。

### 7.4 M8多年度比較オプション

```python
# M8（多年度比較エージェント）がある場合のみセクション追加
try:
    from m8_multiyear_agent import YearDiff
except ImportError:
    YearDiff = None  # オプション依存

if year_diff:
    lines.append("## Section 6. 複数年度比較")
    # 前年比増減、改善トレンド等を追記
```

依存関係は `try/except ImportError` で緩やかに管理する。M8がなくても M5は動作する。

---

## 8. パイプライン連携: E2Eコード例

### 8.1 フル連携の実行例

```python
import os
from scripts.m1_pdf_agent import extract_report
from scripts.m2_law_agent import load_law_context
from scripts.m3_gap_analysis_agent import analyze_gaps
from scripts.m4_proposal_agent import generate_proposals
from scripts.m5_report_agent import generate_report

def run_pipeline(
    pdf_path: str,
    fiscal_year: int = 2025,
    level: str = "竹",
) -> str:
    """M1-M5パイプラインのフル実行"""

    # M1: PDF → StructuredReport
    report = extract_report(pdf_path, fiscal_year=fiscal_year)
    print(f"M1完了: {len(report.sections)}セクション抽出")

    # M2: YAML → LawContext（M1と並列実行可能）
    law_ctx = load_law_context(fiscal_year=fiscal_year)
    print(f"M2完了: {len(law_ctx.applicable_entries)}件の適用法令")

    # M3: StructuredReport × LawContext → GapAnalysisResult
    gap_result = analyze_gaps(report, law_ctx)
    print(f"M3完了: {gap_result.summary.total_gaps}件のギャップ検出")

    # M4: GapAnalysisResult → list[ProposalSet]
    gap_items = [g for g in gap_result.gaps if g.has_gap]
    proposals = generate_proposals(gap_items)
    print(f"M4完了: {len(proposals)}件の提案セット生成")

    # M5: 全出力 → Markdownレポート
    md = generate_report(report, law_ctx, gap_result, proposals, level=level)
    return md

if __name__ == "__main__":
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."
    report_md = run_pipeline("yuho_toyota_2025.pdf")
    with open("output_report.md", "w") as f:
        f.write(report_md)
```

### 8.2 M1とM2の並列実行

M1とM2は**完全に独立**している（入力も出力も異なる）。`concurrent.futures` で並列化できる。

```python
import concurrent.futures

def run_parallel_m1_m2(pdf_path: str, fiscal_year: int):
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_m1 = executor.submit(extract_report, pdf_path, fiscal_year)
        future_m2 = executor.submit(load_law_context, fiscal_year)

        report = future_m1.result()    # M1の完了を待つ
        law_ctx = future_m2.result()   # M2の完了を待つ

    return report, law_ctx
```

単体スクリプト設計ではこの並列化は不可能だ。インターフェース（データクラス）が明確に分離されているからこそ実現できる。

---

## 9. テスト戦略

### 9.1 3層のモック設計

```
Layer 1: PDF非依存テスト（M1のsplit_sections_from_text）
           → unittest / pytest でPDFなしに全テスト

Layer 2: LLM非依存テスト（USE_MOCK_LLM=true）
           → ANTHROPIC_API_KEY不要でM3/M4のパス確認

Layer 3: E2Eテスト（pipeline_mock()）
           → モックデータで全M1-M5のフル連携確認
```

### 9.2 USE_MOCK_LLM による差し替え

```python
# M3/M4では環境変数でLLMをモック化できる
USE_MOCK_LLM=true python3 m3_gap_analysis_agent.py

# m3_gap_analysis_agent.py 内部
def _call_llm(prompt: str) -> str:
    if os.environ.get("USE_MOCK_LLM", "").lower() == "true":
        return json.dumps({
            "has_gap": True,
            "gap_description": "モック: 記載なし",
            "evidence_hint": "モック判定",
            "confidence": "medium",
        })
    # 実LLM呼び出し
    return anthropic.messages.create(...)
```

CI/CDパイプラインではAPIキーなしでテストを完走させる。

### 9.3 pipeline_mock() によるE2Eテスト

```python
# M5に組み込まれたE2Eモックテスト
from m5_report_agent import pipeline_mock

result = pipeline_mock()
assert "開示変更レポート" in result      # ヘッダー確認
assert "## Section 1." in result          # セクション構成確認
assert "免責事項" in result               # 免責文言確認
print(result[:500])
# → Markdownレポートの先頭500文字を確認
```

`pipeline_mock()` はM1〜M5全体をモックデータで動かす**ワンライナーE2Eテスト**だ。デプロイ前の最終確認に使える。

### 9.4 テスト実行例（テスト数と実行時間）

```bash
# M1単体テスト（PDFなし・高速）
python3 -m pytest scripts/test_m1_pdf_agent.py -v
# → 47 passed in 0.2s

# M3テスト（USE_MOCK_LLM=true）
USE_MOCK_LLM=true python3 -m pytest scripts/test_m3_gap_analysis.py -v
# → 30 passed in 0.2s

# 全テスト（408 passed, 19 skipped・モックモード）
USE_MOCK_LLM=true python3 -m pytest scripts/ -v
# → 408 passed, 19 skipped
```

---

## 10. B→C展開戦略

### 10.1 現状: B2B専用ツール（CLI / Streamlit）

現在のM1-M5パイプラインは**大企業のコンプライアンス担当者向け**に設計されている。

```
ユーザー: 上場企業の有報担当者（IR部門・法務部）
使い方: CLIまたはStreamlit UI
課題: PythonとAPIキーのセットアップが必要
```

```bash
# Streamlit UIの起動
cd scripts
ANTHROPIC_API_KEY=sk-ant-... streamlit run app.py
```

Streamlit UIでは、PDFをアップロードするだけでデモモード（`pipeline_mock()`）が動作する。APIキーなしでも動作確認できるのはハードルを下げる重要な設計だ。

### 10.2 Phase 2: APIサーバー化（B2B SaaS）

```
B2B SaaS化のロードマップ:

[Phase 1] CLI/Streamlit → [Phase 2] REST API → [Phase 3] SaaS
                              ↓
              POST /api/v1/analyze
              Content-Type: multipart/form-data
              Authorization: Bearer {api_key}

              {
                "pdf": <binary>,
                "fiscal_year": 2025,
                "level": "竹"
              }

              → { "report_md": "# 開示変更レポート..." }
```

M1-M5の設計が**純粋な関数**（副作用なし・引数→返り値）になっているため、FastAPIラッパーを被せるだけでAPI化できる。

### 10.3 Phase 3: マーケットプレイス展開（B2C）

```
【B2C展開シナリオ】

対象: 中小上場企業・IPO準備企業・個人投資家（開示分析側）

課題:
- 中小企業は有報担当者がいない（兼任）
- IPO準備企業は法令開示経験が浅い
- 個人投資家は開示内容の品質を評価したい

解決策:
- SaaS: 月額課金・PDF1件あたりの単価制
- SDK: 証券会社・監査法人への組み込みライセンス
- API: Marketplace（Zapier / Make / n8n）への統合
```

### 10.4 マルチエージェント設計がもたらすB→C展開の容易さ

M1-M5の分離設計は、機能別の料金設定を可能にする。

```
梅プラン（¥9,800/月）: M1-M3のみ（ギャップ一覧）
竹プラン（¥29,800/月）: M1-M5標準（ギャップ + 文案一覧）
松プラン（¥89,800/月）: M1-M9全体（EDINET自動取得 + 多年度比較 + Word/Excel出力）
```

どのエージェントまで使うかをビジネスモデルに直結させられるのは、**エージェントが明確に分離されているから**だ。

---

## 11. まとめ

M1-M5パイプラインが実現した設計上の成果をまとめる。

| エージェント | 責務 | LLM使用 | テスト容易性 |
|---|---|---|---|
| M1 PDF解析 | PDF→StructuredReport | なし | ✅ PDFなしでテスト可 |
| M2 法令収集 | YAML→LawContext | なし | ✅ ファイルだけで完結 |
| M3 ギャップ分析 | 有報×法令→GapItems | ✅ Haiku | ✅ USE_MOCK_LLM=true |
| M4 松竹梅提案 | GapItems→文案 | ✅ Haiku | ✅ USE_MOCK_LLM=true |
| M5 レポート統合 | 全出力→Markdown | なし | ✅ pipeline_mock() |

**単一責務 × インターフェース契約 × モック設計**の3原則が、408 passed, 19 skipped のテストを持つ保守可能なコードベースを実現した。

### 次回予告

次回は **Phase 2: EDINET自動取得 × M6法令URL収集 × M8多年度比較** を解説する。EDINET APIv2の認証不要エンドポイントを活用した、コスト実質ゼロの有報自動取得パイプラインだ。

---

:::details 環境構築（参考）

```bash
# リポジトリクローン
git clone https://github.com/Majiro-ns/disclosure-multiagent.git
cd disclosure-multiagent

# 依存パッケージ
pip install pymupdf pyyaml anthropic streamlit

# モックモードで動作確認（APIキー不要）
cd scripts
USE_MOCK_LLM=true python3 m3_gap_analysis_agent.py

# E2Eテスト
python3 -c "from m5_report_agent import pipeline_mock; print(pipeline_mock()[:500])"
```

:::

---

*著者: disclosure-multiagentプロジェクト / 2026-03-09*
