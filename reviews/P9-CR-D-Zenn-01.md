# P9-CR-D-Zenn-01: disclosure Zenn記事① クロスレビュー

| 項目 | 内容 |
|---|---|
| レビューID | P9-CR-D-Zenn-01 |
| 対象タスク | D-Zenn-01（足軽6作成）+ D-Zenn-01-fix（26bd09f適用済み） |
| 対象ファイル | docs/article_disclosure_phase1_draft.md |
| レビュー実施 | 足軽7（cmd_345k_2） |
| レビュー日時 | 2026-03-09 |
| 最終判定 | ⚠️ **条件付き承認**（必須修正3件） |

---

## 前提: 旧CR適用確認

足軽8（fab8877）指摘の必須修正5件が 26bd09f で適用済みであることを grep 確認。

| 旧CR項目 | 修正内容 | 状態 |
|---------|---------|------|
| M1旧 | `_keyword_check`/`analyze_gap_with_llm` 擬似コード注記 | ✅ L163-184 |
| M2旧 | `USE_MOCK_LLM` デフォルト `""` に修正 | ✅ L185 |
| M3旧 | `FEW_SHOT_EXAMPLES` 構造 `{section_name:{level:text}}` | ✅ L211-230 |
| M4旧 | `generate_proposal` シグネチャ `section_name: str` 5引数 | ✅ L232-238 |
| M5旧 | `/path/to/your/annual_report.pdf` へ修正 | ✅ L289-292 |

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
| 文量 9,500字以上 | ✅ |
| コードブロック（python/yaml/bash）形式 | ✅ |
| 外部リンク（L458-460） | ✅ |

**CR-5 判定: ✅ PASS**

---

## CR-1: パイプライン説明と実装の一致確認

### データクラス名照合

記事（Section 2.1 アーキテクチャ図）のデータクラスを実装ファイルで確認。

| 記事の名称 | 実装の定義場所 | 判定 |
|-----------|-------------|------|
| `StructuredReport` | m3_gap_analysis_agent.py L118（m1からimport） | ✅ |
| `LawContext` | m3_gap_analysis_agent.py L151 | ✅ |
| `GapAnalysisResult` / `GapItem` | m3_gap_analysis_agent.py L166, L221 | ✅ |
| `ProposalResult` | m4_proposal_agent.py L118（ProposalSet） | ✅（名称は ProposalSet） |

### M1: `extract_sections()` 関数名 ⚠️（必須修正 M-1）

**記事 L108:**
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

| 記事の名称 | 実装の実際 | 判定 |
|-----------|-----------|------|
| `extract_sections()` | `extract_report()` (L258) | ❌ |
| `generate_doc_id()` | `_make_document_id()` (L383、プライベート) | ❌ |
| `extract_company_name()` | `_extract_company_name()` (L390、プライベート) | ❌ |
| `extract_fiscal_year()` | 独立関数として存在しない（引数として渡す） | ❌ |
| `split_sections_from_text()` | `split_sections_from_text()` (L147) | ✅ |

M3の擬似コードと異なり、M1コードには「擬似コード」注記がない。読者がコピペ実行した場合 `AttributeError` が発生する。

実際の `extract_report()` シグネチャ:
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

### M1: 「13のキーワード」（L128）

記事: 「13のキーワード（「第一部」「企業情報」「第二部」「財務情報」「人的資本」等）を正規表現でマッチング」

実装: `HEADING_PATTERNS`（8パターンの正規表現）。「13」の根拠不明。→ 推奨修正（後述 R-1）

### M1: WARNINGメッセージ（L123）

```
WARNING m1_pdf_agent:m1_pdf_agent.py:263 PDF開封エラー（空sectionsで継続）
```

実装 L319: `logger.warning("PDF開封エラー（空sectionsで継続）: %s", e)` ✅（内容一致）

### M3: 擬似コード注記（旧CR修正済み）✅

- L163: `_keyword_check` 擬似コード注記 ✅
- L180: `analyze_gap_with_llm` 擬似コード注記 ✅
- L184: `judge_gap()` 実装シグネチャ明記 ✅

照合: m3_gap_analysis_agent.py L336 `def judge_gap(...)` ✅

### M4: `generate_proposal` シグネチャ（旧CR修正済み）✅

記事 L232-238（修正済み）:
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

### M4: モデルID ⚠️（必須修正 M-2）

**記事 L243:**
```python
    model="claude-haiku-4-5",
```

**実装照合（m4_proposal_agent.py L42）:**
```python
MODEL = "claude-haiku-4-5-20251001"
```

日付サフィックス `-20251001` が欠落。読者がこのモデルIDでAPI呼び出した場合、モデルが見つからないエラーが発生する可能性がある。

### M5: `_is_streamlit_running()` の帰属（推奨修正 R-2）

記事（L264-273）はM5の実装として紹介しているが、実際は `scripts/app.py` L390 に存在（`m5_report_agent.py` には存在しない）。

**CR-1 判定: ⚠️ FAIL（M-1: extract_sections注記・M-2: モデルID）**

---

## CR-2: コードスニペット詳細検証

### USE_MOCK_LLM（旧CR修正済み）✅

L185: `use_mock = os.environ.get("USE_MOCK_LLM", "").lower() in ("true", "1", "yes")`

m3_gap_analysis_agent.py L551 と一致 ✅

### FEW_SHOT_EXAMPLES 構造（旧CR修正済み）✅

L211-230: `{"従業員給与等の決定に関する方針": {"松": ..., "竹": ..., "梅": ...}}`

m4_proposal_agent.py L148 の `{section_name: {level: text}}` 構造と一致 ✅

### M2 YAMLスニペット（L134-153）⚠️（必須修正 M-3）

**記事のYAMLスニペット（L135-153）:**
```yaml
# law_entries_human_capital.yaml（抜粋）
law_entries:
  - entry_id: HC_20260220_001
    ...
    required_items:
      - keyword: "企業戦略と関連付"
        change_type: mandatory_addition
```

**実装照合（laws/human_capital_2024.yaml）:**

| 記事の記述 | 実際の実装 | 判定 |
|-----------|-----------|------|
| ファイル名 `law_entries_human_capital.yaml` | `human_capital_2024.yaml` | ❌ |
| キー `law_entries:` | `amendments:` | ❌ |
| フィールド `entry_id: HC_20260220_001` | `id: hc-2024-001` | ❌ |
| `required_items[].keyword` 形式 | `required_items` は文字列リスト | ❌ |

M1・M3の擬似コードと異なり、このYAMLスニペットには「設計概念」「擬似」の注記がない。実際のスキーマ（`amendments`/`id`/文字列リスト）と全面乖離しており、読者が同形式でYAMLを作成しても読み込めない。

### 実行コマンド（L291-296）✅

```bash
python3 scripts/run_e2e.py \
    "/path/to/your/annual_report.pdf" \
    --company-name "トヨタ自動車" \
    ...
```

`/path/to/your/annual_report.pdf` はプレースホルダとして正確 ✅（旧CR M5修正済み）

**CR-2 判定: ⚠️ FAIL（M-3: M2 YAMLスキーマ形式）**

---

## CR-3: デモ結果の正確性確認 ✅

### 検出7件の根拠ID確認

| 項目 | 根拠ID | YAMLとの整合 |
|------|-------|------------|
| 企業戦略と関連付けた人材戦略 | HC_20260220_001 | ✅（hc-2024-001相当） |
| 従業員給与等の決定に関する方針 | HC_20260220_001 | ✅ |
| 平均年間給与の対前事業年度増減率 | HC_20260220_001 | ✅ |
| 人材戦略と経営戦略の連動 | HC_20250421_001 | ✅ |
| 定量的KPI・目標値 | HC_20250421_001 | ✅ |
| ガバナンス体制の開示例 | HC_20250421_001 | ✅ |
| リスク・機会の開示例 | HC_20250421_001 | ✅ |

追加必須3件・修正推奨4件の分類も一致 ✅

### テスト件数

記事 L46・L443: 「207件のテスト全PASS確認済み」
Phase1モジュール（m1:47+m2:26+m3:23+m4:48+m5:46=190件）。記事はPhase1紹介のため、207件はPhase1当時（E2E含む）の件数として整合範囲内と判断。→ 推奨修正（R-3）

**CR-3 判定: ✅ PASS**

---

## CR-4: 法令情報の正確性 ✅

### 主要法令記述

| 記事の記述 | 確認 |
|-----------|------|
| 「企業内容等の開示に関する内閣府令改正（2026年2月）」 | human_capital_2024.yaml hc-2024-001〜004と整合 ✅ |
| 「金融庁WG好事例集（2025年4月）」HC_20250421_001 | human_capital_2024.yaml に対応エントリあり ✅ |
| 「4層の幻覚防止機構」（L159-198） | m3の設計概念と一致 ✅ |
| 「法令情報のYAML管理」（L43-44, L155） | m2実装と整合 ✅ |

**CR-4 判定: ✅ PASS**

---

## 指摘事項サマリー

### 必須修正（3件）

| ID | 重大度 | 箇所 | 内容 |
|----|-------|------|------|
| **M-1** | 🔴 高 | L105-118（M1コード） | `extract_sections()` 等の関数名が実装と異なり、擬似コード注記がない |
| **M-2** | 🔴 高 | L243（M4コード） | `model="claude-haiku-4-5"` → 実装は `"claude-haiku-4-5-20251001"` |
| **M-3** | 🔴 高 | L134-153（M2 YAML） | `law_entries`/`HC_20260220_001`/`keyword`形式が実実装と全面乖離、擬似YAML注記なし |

### 推奨修正（3件）

| ID | 箇所 | 内容 |
|----|------|------|
| R-1 | L128 | 「13のキーワード」→ HEADING_PATTERNSは8パターン |
| R-2 | L264-273 | `_is_streamlit_running()` は `app.py` 所在（M5ではない） |
| R-3 | L46, L443 | テスト件数「207件」→ 現在の実績値（190+22件または293件）に更新推奨 |

---

## 修正指示

### M-1（必須）: M1コードスニペットへの擬似コード注記追加

`docs/article_disclosure_phase1_draft.md` L105直前に以下を追加:

```markdown
> ※ 以下は設計概念を示す擬似コードです。実際のメインAPIは `extract_report()` 関数
> （`scripts/m1_pdf_agent.py`）として実装されています。
```

または `extract_sections` → `extract_report` に関数名を変更し、実際のシグネチャに合わせる。

### M-2（必須）: M4モデルIDのサフィックス追加

L243を修正:
```python
# 修正前
model="claude-haiku-4-5",

# 修正後
model="claude-haiku-4-5-20251001",
```

### M-3（必須）: M2 YAMLスニペットへの擬似YAML注記追加

L134直前に以下を追加:

```markdown
> ※ 以下は設計概念を示す擬似 YAML です。実際のスキーマは `amendments:` キー・
> `id: "hc-2024-001"` 形式・`required_items` は文字列リストを使用します。
> 詳細は `laws/human_capital_2024.yaml` および `docs/law_yaml_schema.md` を参照ください。
```

---

## 最終判定

```
⚠️ 条件付き承認
必須修正3件（M-1〜M-3）修正・git commit後に正式承認
```

旧CR（fab8877）で指摘の5件は全て 26bd09f で適用済み ✅
今回新規発見: M1擬似コード注記・M4モデルID・M2 YAMLスキーマ形式の3件
法令情報・B2C戦略・デモ結果・Zenn要件は全て PASS

---

*レビュー実施: 足軽7 / P9-CR-D-Zenn-01 / 2026-03-09*
*照合ファイル: m1_pdf_agent.py / m2_law_agent.py / m3_gap_analysis_agent.py / m4_proposal_agent.py / m5_report_agent.py / app.py / laws/human_capital_2024.yaml*
