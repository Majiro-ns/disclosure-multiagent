# P9-CR-D-Zenn-01-v2: disclosure Zenn記事① 独立クロスレビュー

| 項目 | 内容 |
|---|---|
| レビューID | P9-CR-D-Zenn-01-v2 |
| 対象ファイル | `docs/article_disclosure_phase1_draft.md`（462行） |
| レビュー実施 | 足軽7（cmd_345k_2） |
| レビュー日時 | 2026-03-10 |
| 照合対象 | m1〜m5実装ファイル / laws/human_capital_2024.yaml / scripts/app.py |
| 最終判定 | ⚠️ **条件付き承認**（必須修正3件・推奨修正3件） |

---

## 前提: 既存CR適用状況の確認

| 既存CR | commit | 状況 |
|--------|--------|------|
| 初回CR（ashigaru8 fab8877）5件 | 26bd09f | **全5件適用済み** ✅ |
| 2回目CR（足軽7 4da475a）3件 | — | **未適用** ⚠️ |

**旧CR5件（26bd09f）適用確認:**

| 旧CR項目 | 確認箇所 | 状態 |
|---------|---------|------|
| `_keyword_check` 擬似コード注記 | L163-172 | ✅ |
| `analyze_gap_with_llm` 擬似コード注記 | L180-184 | ✅ |
| `USE_MOCK_LLM` デフォルト `""` | L185 | ✅ |
| `FEW_SHOT_EXAMPLES` `{section_name:{level:text}}` | L211-230 | ✅ |
| `generate_proposal` 5引数・`/path/to/your/annual_report.pdf` | L232-238, L291-296 | ✅ |

---

## CR-5: Zenn要件確認（先行チェック） ✅

### frontmatter（L1-7）

```yaml
---
title: "AIで有価証券報告書の開示漏れを自動検出する — Pythonマルチエージェント実装"
emoji: "📋"
type: "tech"
topics: ["python", "ai", "有報", "開示"]
published: false
---
```

| 要件 | 確認 |
|------|------|
| `title` | ✅ |
| `emoji` | ✅ |
| `type: "tech"` | ✅ |
| `topics: ["python", "ai", "有報", "開示"]` | ✅ |
| `published: false` | ✅ |

### 構成・文量

| 項目 | 確認 |
|------|------|
| 5節構成（課題/アーキテクチャ/実装詳細/デモ結果/B→C戦略） | ✅ |
| 文量 462行（9,000字以上） | ✅ |
| コードブロック（python/yaml/bash） | ✅ |
| 外部リンク（L458-460） | ✅ |

**CR-5 判定: ✅ PASS**

---

## CR-1: M1パイプライン説明と実装の照合

### M1コードスニペット（L105-118）⚠️（必須修正 M-1）

**記事 L108-117:**
```python
def extract_sections(pdf_path: str) -> StructuredReport:
    doc = fitz.open(pdf_path)
    full_text = "\n".join(page.get_text() for page in doc)
    sections = split_sections_from_text(full_text)
    return StructuredReport(
        document_id=generate_doc_id(pdf_path),
        company_name=extract_company_name(full_text),
        fiscal_year=extract_fiscal_year(full_text),
        sections=sections,
    )
```

**m1_pdf_agent.py 照合結果:**

| 記事の記述 | 実装の実際 | 行 | 判定 |
|-----------|-----------|-----|------|
| `extract_sections()` | `extract_report()` | L258 | ❌ |
| `generate_doc_id(pdf_path)` | `_make_document_id(path)` (プライベート) | L383 | ❌ |
| `extract_company_name(full_text)` | `_extract_company_name(full_text, path)` (プライベート・2引数) | L390 | ❌ |
| `extract_fiscal_year(full_text)` | `fiscal_year` 引数で外部から渡す（独立関数なし） | — | ❌ |
| `split_sections_from_text(full_text)` | `split_sections_from_text(full_text, doc_type=doc_type)` | L345 | △（defaultあり・動作可） |

**問題点**: このコードブロックに「擬似コード」注記がない。読者がコピペ実行すると `NameError: extract_sections is not defined` が発生する。M3の類似コード（L163）には旧CRで注記が追加されているが、M1（L105-118）には注記がない。

**実際の `extract_report()` シグネチャ（m1_pdf_agent.py L258-265）:**
```python
def extract_report(
    pdf_path: str,
    fiscal_year: Optional[int] = None,
    fiscal_month_end: int = 3,
    company_name: str = "",
    extract_tables: bool = True,
    doc_type: str = "yuho",
) -> StructuredReport:
```

### M1 WARNING メッセージ（L122-124）✅

記事:
```
WARNING m1_pdf_agent:m1_pdf_agent.py:263 PDF開封エラー（空sectionsで継続）: '.' is no file
```

実装（m1_pdf_agent.py L319）:
```python
logger.warning("PDF開封エラー（空sectionsで継続）: %s", e)
```

✅ メッセージ内容一致

### M1「13のキーワード」（L128）（推奨修正 R-1）

記事: 「13のキーワード（「第一部」「企業情報」「第二部」「財務情報」「人的資本」等）を正規表現でマッチング」

実装（m1_pdf_agent.py L60-69）: `HEADING_PATTERNS` は **8パターン**の正規表現リスト。「13」の根拠は確認できない。

### M3 擬似コード注記（旧CR適用済み）✅

- L163-172: `_keyword_check` 擬似コード注記 ✅
- L180-184: `analyze_gap_with_llm` 擬似コード注記 ✅
- L184: `judge_gap()` 実装シグネチャ明記 ✅

### M4 `generate_proposal` シグネチャ（旧CR適用済み）✅

記事 L232-239（修正済み）:
```python
def generate_proposal(
    section_name: str,
    change_type: str,
    law_summary: str,
    law_id: str,
    level: str,
    system_prompt: Optional[str] = None,
) -> str:
```

m4_proposal_agent.py L625-632 と一致 ✅

**CR-1 判定: ⚠️ FAIL（M-1: extract_sections擬似コード注記なし）**

---

## CR-2: コードスニペット詳細検証

### USE_MOCK_LLM（旧CR適用済み）✅

L185: `use_mock = os.environ.get("USE_MOCK_LLM", "").lower() in ("true", "1", "yes")`

デフォルト `""` → 環境変数未設定でfalse（本番モード） ✅

### FEW_SHOT_EXAMPLES 構造（旧CR適用済み）✅

L211-230: `{"従業員給与等の決定に関する方針": {"松": ..., "竹": ..., "梅": ...}}`

m4_proposal_agent.py L148 の `{section_name: {level: text}}` 構造と一致 ✅

### M4 モデルID（L242）⚠️（必須修正 M-2）

**記事 L242:**
```python
    model="claude-haiku-4-5",
```

**実装照合（m4_proposal_agent.py L42）:**
```python
MODEL = "claude-haiku-4-5-20251001"
```

日付サフィックス `-20251001` が欠落。記事の通りのモデルIDでAPI呼び出しを行うとモデルが見つからないエラーが発生する可能性がある。

### M2 YAMLスニペット（L134-153）⚠️（必須修正 M-3）

**記事のYAMLスニペット（L135-153）:**
```yaml
# law_entries_human_capital.yaml（抜粋）
law_entries:
  - entry_id: HC_20260220_001
    law_name: 企業内容等の開示に関する内閣府令改正...
    ...
    required_items:
      - keyword: "企業戦略と関連付"
        description: "..."
        change_type: mandatory_addition
```

**実装照合（laws/human_capital_2024.yaml）:**

| 記事の記述 | 実際の実装 | 判定 |
|-----------|-----------|------|
| ファイル名 `law_entries_human_capital.yaml` | `human_capital_2024.yaml` | ❌ |
| トップレベルキー `law_entries:` | `amendments:` | ❌ |
| `entry_id: HC_20260220_001` | `id: "hc-2024-001"` | ❌ |
| `required_items[].keyword` 形式（辞書リスト） | `required_items` は文字列リスト（例: `"人材の確保・育成・定着の方針"`） | ❌ |

4項目全面乖離。擬似コード注記なし。読者が記事を参考にYAMLを作成しても `m2_law_agent.py` で正しく読み込めない。

### M5 `_is_streamlit_running()`（推奨修正 R-2）

記事（L264-273）: M5の実装として `_is_streamlit_running()` を紹介。

実装照合:
- `scripts/m5_report_agent.py`: `_is_streamlit_running()` **存在しない**
- `scripts/app.py` **L390**: `def _is_streamlit_running() -> bool:` に存在

帰属が誤り（M5ではなくapp.py）。

**CR-2 判定: ⚠️ FAIL（M-2: モデルID・M-3: M2 YAMLスキーマ形式）**

---

## CR-3: デモ結果の正確性確認 ✅

### 検出7件の構成

| 変更種別 | 件数 | 根拠ID |
|----------|------|-------|
| 追加必須 | 3 | HC_20260220_001（hc-2024-xxx相当） |
| 修正推奨 | 4 | HC_20250421_001 |
| 合計 | 7 | — |

根拠ID `HC_20260220_001` / `HC_20250421_001` の記述は `laws/human_capital_2024.yaml` の `hc-2024-xxx` エントリと整合 ✅

### テスト件数「207件」（推奨修正 R-3）

記事 L46・L443: 「207件のテスト全PASS確認済み」

Phase1モジュール現在の実績（m1:47+m2:26+m3:23+m4:48+m5:46=190件）。207件はPhase1当時のE2E含む件数として整合範囲内。ただし現行値との乖離あり → 更新推奨。

### PDFパス（L291-296）✅

`/path/to/your/annual_report.pdf` → プレースホルダとして正確 ✅（旧CR M5修正済み）

**CR-3 判定: ✅ PASS**

---

## CR-4: 法令情報の正確性 ✅

| 記事の記述 | 確認 |
|-----------|------|
| 「企業内容等の開示に関する内閣府令改正（2026年2月）」 | laws/human_capital_2024.yaml hc-2024-001〜004と整合 ✅ |
| 「金融庁WG好事例集（2025年4月）」HC_20250421_001 | human_capital_2024.yaml に対応エントリあり ✅ |
| 「4層の幻覚防止機構」（L159-198） | m3の設計概念と一致 ✅ |
| 法令情報のYAML管理（L43-44, L155） | m2実装と整合 ✅ |
| B→C戦略（Section 5）の記述 | 実装と矛盾なし ✅ |

**CR-4 判定: ✅ PASS**

---

## 指摘事項サマリー

### 必須修正（3件）

| ID | 重大度 | 箇所 | 内容 |
|----|-------|------|------|
| **M-1** | 🔴 高 | L105-118（M1コードブロック） | `extract_sections()` 等の関数名が実装と相違し擬似コード注記がない（実装: `extract_report()` / `_make_document_id()` / `_extract_company_name()`） |
| **M-2** | 🔴 高 | L242（M4モデルID） | `model="claude-haiku-4-5"` → 実装は `"claude-haiku-4-5-20251001"`（日付サフィックス欠落） |
| **M-3** | 🔴 高 | L134-153（M2 YAMLスニペット） | ファイル名/トップレベルキー/IDフォーマット/required_items形式が実実装と全面乖離・擬似YAML注記なし |

### 推奨修正（3件）

| ID | 箇所 | 内容 |
|----|------|------|
| R-1 | L128 | 「13のキーワード」→ HEADING_PATTERNSは8パターン |
| R-2 | L264-273 | `_is_streamlit_running()` はapp.py L390（m5_report_agent.pyではない） |
| R-3 | L46, L443 | テスト件数「207件」→ 現行実績値（190+件）に更新推奨 |

---

## 修正指示

### M-1（必須）: M1コードスニペットへの擬似コード注記追加

`docs/article_disclosure_phase1_draft.md` L105直前に以下を追加:

```markdown
> ※ 以下は設計概念を示す擬似コードです。実際のメインAPIは `extract_report()` 関数
> （`scripts/m1_pdf_agent.py` L258）として実装されています。
> ヘルパー関数 `generate_doc_id` / `extract_company_name` / `extract_fiscal_year` は
> プライベート実装（`_make_document_id` / `_extract_company_name`）として存在します。
```

または記事のコードを実装に合わせて書き直す（`extract_report()` シグネチャを使用）。

### M-2（必須）: M4モデルIDのサフィックス追加

L242を修正:
```python
# 修正前
    model="claude-haiku-4-5",

# 修正後
    model="claude-haiku-4-5-20251001",
```

### M-3（必須）: M2 YAMLスニペットへの擬似YAML注記追加

L134直前に以下を追加:

```markdown
> ※ 以下は設計概念を示す擬似YAMLです。実際のスキーマは `amendments:` キー・
> `id: "hc-2024-001"` 形式・`required_items` は文字列リストを使用します。
> 詳細は `laws/human_capital_2024.yaml` および `docs/law_yaml_schema.md` を参照ください。
```

---

## 最終判定

```
⚠️ 条件付き承認
必須修正3件（M-1〜M-3）修正・git commit後に正式承認
```

旧CR（fab8877）指摘の5件は全て 26bd09f で適用済み ✅
足軽7 前回CR（4da475a）指摘のM-1〜M-3は未適用のまま ⚠️
法令情報・B→C戦略・デモ結果・Zenn要件は全て PASS ✅

---

*レビュー実施: 足軽7 / P9-CR-D-Zenn-01-v2 / 2026-03-10*
*照合ファイル: m1_pdf_agent.py / m2_law_agent.py / m3_gap_analysis_agent.py / m4_proposal_agent.py / m5_report_agent.py / app.py / laws/human_capital_2024.yaml*
