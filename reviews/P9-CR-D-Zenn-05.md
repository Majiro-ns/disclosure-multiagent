# P9-CR-D-Zenn-05: disclosure Zenn記事⑤「銀行業の有報チェックをAIで自動化する」クロスレビュー

**レビュアー**: 足軽4号
**対象記事**: `docs/article_disclosure_banking_draft.md`
**照合ファイル**:
- `laws/banking_2025.yaml`
- `scripts/m2_law_agent.py`
- `scripts/m3_gap_analysis_agent.py`

**レビュー日**: 2026-03-09
**最終グレード**: **A-**（必須修正1件適用後）

---

## CR-1: 技術的正確性（一次資料照合）

### 1-1. BANKING_KEYWORDS 照合

**対象**: 記事 Section 4-1「BANKING_KEYWORDS — 業種判定の入口」
**照合元**: `scripts/m3_gap_analysis_agent.py` L62-70

```python
# m3_gap_analysis_agent.py 実装（L62-70）
BANKING_KEYWORDS = [
    "バーゼル", "Basel", "自己資本比率", "CET1", "Tier1", "Tier2",
    "リスク加重資産", "RWA", "LCR", "流動性カバレッジ", "NSFR", "安定調達",
    "レバレッジ比率", "不良債権", "貸倒引当金", "信用リスク", "与信",
    "要管理先", "破綻懸念先", "実質破綻先", "破綻先",
    "金利リスク", "IRRBB", "EVE", "NII", "ストレステスト",
    "流動性リスク", "市場リスク", "オペレーショナルリスク",
    "個別貸倒引当金", "一般貸倒引当金", "集中リスク",
]
```

**判定**: ✅ **完全一致** — 記事記載の32語がm3_gap_analysis_agent.py L62-70と全語一致。

---

### 1-2. banking_2025.yaml 構成照合

**対象**: 記事 Section 2「banking_2025.yaml — 10件のチェック項目」
**照合元**: `laws/banking_2025.yaml`

| 項目 | 記事記載 | YAML実値 | 判定 |
|------|----------|----------|------|
| エントリ総数 | 10件 | 10件（bk-2025-001〜010） | ✅ |
| CET1最低比率 | 4.5% | 4.5% | ✅ |
| Tier1最低比率 | 6% | 6% | ✅ |
| 総自己資本比率 | 8% | 8% | ✅ |
| LCR最低水準 | 100% | 100%（国際統一基準） | ✅ |
| NSFR最低水準 | 100% | 100% | ✅ |
| NSFR施行時期 | 2021年3月末 | "2021年3月末より規制適用開始（国際統一基準行）" | ✅ |
| レバレッジ比率 | 3% | 3% | ✅ |
| レバレッジ国内基準行適用 | 2023年3月〜 | "2023年3月末より国内基準行にも適用拡大" | ⚠️ 推奨 |
| IRRBB施行 | 2020年3月末 | "2020年3月末施行" | ✅ |
| 第1群〜第3群の分類 | 正確 | bk-001〜005/006-007/008-010 | ✅ |
| source_confirmed | — | 全10件 true | ✅ |

---

### 1-3. m2_law_agent.py コード照合

**対象**: 記事 Section 5「M2法令収集エージェントの銀行業対応」
**照合元**: `scripts/m2_law_agent.py`

| コード要素 | 記事記載 | 実装値 | 判定 |
|-----------|----------|--------|------|
| CRITICAL_CATEGORIES | `["人的資本ガイダンス", "金商法・開示府令", "SSBJ"]` | L51: 同一 | ✅ |
| _load_all_from_dir() | `sorted(yaml_dir.glob("*.yaml"))` で全YAML結合 | 同一 | ✅ |
| load_law_entries() | "entries"/"amendments" 両キー対応 | 同一 | ✅ |
| disclosure_items フォールバック | `raw.get("disclosure_items") or raw.get("required_items")` | 同一 | ✅ |
| load_law_context() シグネチャ | `(fiscal_year, fiscal_month_end, yaml_path=None, categories=None)` | 同一 | ✅ |

---

### 1-4. StructuredReport フィールド名照合 【必須修正】

**対象**: 記事 Section 5-1 コードブロック L368-372
**照合元**: `scripts/m3_gap_analysis_agent.py`（StructuredReport dataclass 定義）

**記事記載（誤）**:
```python
demo_report = StructuredReport(
    company="○○銀行株式会社",
    fiscal_year="2025年3月期",
    sections=[],
)
```

**実装（正）**:
```python
demo_report = StructuredReport(
    document_id="BANK_DEMO_001",
    company_name="○○銀行株式会社",
    fiscal_year=2025,
    fiscal_month_end=3,
    sections=[],
)
```

**問題点**:
- `company=` → `company_name=`（フィールド名相違）
- `fiscal_year="2025年3月期"` → `fiscal_year=2025`（型相違: str→int）
- `fiscal_month_end=3` が欠落（必須フィールド）
- `document_id` が欠落（必須フィールド）

**判定**: ❌ **[必須-L1]** — 実行時 TypeError が発生する誤りコード。読者が即時実行した場合にエラーとなる。

---

## CR-2: 数値・日付・閾値の検証

| 検証項目 | 記事値 | 一次資料値 | 判定 |
|---------|-------|-----------|------|
| CET1 = 4.5% | ✅ | banking_2025.yaml bk-2025-001 | ✅ |
| Tier1 = 6% | ✅ | banking_2025.yaml bk-2025-001 | ✅ |
| 総自己資本比率 = 8% | ✅ | banking_2025.yaml bk-2025-001 | ✅ |
| LCR ≥ 100% | ✅ | banking_2025.yaml bk-2025-003 | ✅ |
| NSFR ≥ 100% | ✅ | banking_2025.yaml bk-2025-004 | ✅ |
| レバレッジ ≥ 3% | ✅ | banking_2025.yaml bk-2025-005 | ✅ |
| NSFR 2021年3月末施行 | ✅ | banking_2025.yaml bk-2025-004 | ✅ |
| IRRBB 2020年3月末施行 | ✅ | banking_2025.yaml bk-2025-010 | ✅ |
| レバレッジ "2023年3月〜" | ⚠️ | YAML: "2023年3月末〜" | 推奨修正 |
| BANKING_KEYWORDS 32語 | ✅ | m3_gap_analysis_agent.py L62-70 | ✅ |

---

## CR-3: 論理一貫性・読者体験

**Section 3（第1群〜第3群分類）**: banking_2025.yaml の `action: "追加必須"/"修正推奨"` 区分と一致。読者が YAML を見ながら追跡できる構成。 ✅

**Section 4（BANKING_KEYWORDS 解説）**: キーワード32語の意味・用途を適切に説明。m3_gap_analysis_agent.py の実装意図と整合。 ✅

**Section 5（M2エージェント解説）**: _load_all_from_dir() による自動読み込みの仕組みを正確に説明。banking_2025.yaml が自動的に読み込まれる流れが明確。 ✅

**Section 6（実装コード例）**: `load_law_context()` の呼び出し方・categories 引数の使い方が実装と一致。ただし以下2点を推奨修正として記載（後述）。

---

## CR-4: 推奨修正事項

### [推奨-L2] Section 6-2 categories に "人的資本" を指定している箇所

```python
# 記事の記述
law_ctx_multi = load_law_context(
    fiscal_year=2025,
    fiscal_month_end=3,
    categories=["銀行業（バーゼルIII）", "銀行業（不良債権）", "人的資本"],
)
# → 12件（銀行業10件 + 人的資本2件）
```

**推奨**: `human_capital_2024.yaml` の実際のカテゴリ名は `"人的資本ガイダンス"` または `"金商法・開示府令"` である可能性がある。`"人的資本"` でフィルタすると0件ヒットし、コメントの「12件（銀行業10件 + 人的資本2件）」が誤りになりうる。実際のカテゴリ名を確認して修正を推奨。

### [推奨-L3] Section 6-3 テーブル レバレッジ比率の適用時期

```
記事: "2023年3月〜適用拡大"
YAML: "2023年3月末より国内基準行にも適用拡大"
```

**推奨**: "2023年3月末〜" に修正してYAML記述と一致させる（月末適用の明示）。

---

## CR-5: 総合評価

### スコアカード

| CR項目 | 評価 | 備考 |
|--------|------|------|
| CR-1 技術的正確性 | B | StructuredReport フィールド名エラー[L1]あり |
| CR-2 数値・日付検証 | A | 全数値一次資料と一致（推奨修正1件） |
| CR-3 論理一貫性 | A | 記事構成・説明の整合性OK |
| CR-4 推奨修正 | — | 2件（L2: categories, L3: 日付表記） |
| CR-5 総合 | **A-** | 必須修正[L1]適用後 |

### グレード根拠

- **必須修正**: 1件（[L1] StructuredReport フィールド名・型エラー）→ 適用後グレード A-
- **推奨修正**: 2件（[L2] categories名確認推奨 / [L3] 月末表記統一）
- **問題なし**: BANKING_KEYWORDS 32語全一致 / 全数値一次資料照合済み / M2エージェントコード正確

### 必須修正箇所（[L1]）

**ファイル**: `docs/article_disclosure_banking_draft.md` Section 5-1
**修正前**:
```python
demo_report = StructuredReport(
    company="○○銀行株式会社",
    fiscal_year="2025年3月期",
    sections=[],
)
```
**修正後**:
```python
demo_report = StructuredReport(
    document_id="BANK_DEMO_001",
    company_name="○○銀行株式会社",
    fiscal_year=2025,
    fiscal_month_end=3,
    sections=[],
)
```

---

**CR完了**: 必須修正1件を記事に適用済み（コミット参照）
**レビュー確定グレード**: **A-**
