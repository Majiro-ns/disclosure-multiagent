# P9-CR-D-Zenn-04b: disclosure Zenn記事④ クロスレビュー

| 項目 | 内容 |
|---|---|
| レビューID | P9-CR-D-Zenn-04b |
| 対象ファイル | `docs/article_disclosure_batch_draft.md`（732行） |
| レビュー実施 | 足軽7（cmd_345k_2） |
| レビュー日時 | 2026-03-09 |
| 照合対象 | m6_law_url_collector.py / m7_edinet_client.py / m8_multiyear_agent.py / laws/ |
| 最終判定 | ⚠️ **条件付き承認**（必須修正2件・推奨修正2件） |

---

## CR-5: Zenn要件確認（先行チェック） ✅

### frontmatter（L1-7）

```yaml
---
title: "EDINETから有報を一括取得して多年度比較する — M6-M8バッチ処理実装"
emoji: "📊"
type: "tech"
topics: ["python", "edinet", "有価証券報告書", "llm", "バッチ処理"]
published: false
---
```

| 要件 | 確認 |
|------|------|
| `title` | ✅ |
| `emoji` | ✅ |
| `type: "tech"` | ✅ |
| `topics` 5項目 | ✅ |
| `published: false` | ✅ |

### 構成・文量

| 項目 | 確認 |
|------|------|
| 9節構成（はじめに/M7/M6/M8/E2E/EDINET申請/テスト/活用パターン/まとめ） | ✅ |
| 文量 732行 | ✅（8,000字超） |
| コードブロック（python/yaml/bash）形式 | ✅ |

**CR-5 判定: ✅ PASS**

---

## CR-1: M7 実装との照合

### 主要関数・定数（m7_edinet_client.py）

| 記事の記述 | 実装 | 判定 |
|-----------|------|------|
| `EDINET_API_BASE = "https://api.edinet-fsa.go.jp/api/v2"` (L63) | L16: `EDINET_API_BASE = "https://api.edinet-fsa.go.jp/api/v2"` | ✅ |
| `validate_edinetcode(code: str) -> bool` (L73) | L34: `def validate_edinetcode(code: str) -> bool:` | ✅ |
| `validate_doc_id(doc_id: str) -> bool` (L78) | L39: `def validate_doc_id(doc_id: str) -> bool:` | ✅ |
| `fetch_document_list(date: str, doc_type_code: str = "120")` (L92) | L44: 同一シグネチャ | ✅ |
| `download_pdf(doc_id: str, output_dir: str) -> str` (L118) | L65: 同一シグネチャ | ✅ |
| `search_by_company(company_name: str, year: int)` (L149) | L91: 同一シグネチャ | ✅ |

### EDINET URL構成

| 記事の記述 | 実装 | 判定 |
|-----------|------|------|
| 書類一覧 URL `{EDINET_API_BASE}/documents.json` (L104) | L56: `f"{EDINET_API_BASE}/documents.json"` | ✅ |
| PDF DL `{EDINET_DL_BASE}/{doc_id}.pdf` (L130) | L15: `EDINET_DL_BASE = "https://disclosure2dl.edinet-fsa.go.jp/searchdocument/pdf"` L77: `f"{EDINET_DL_BASE}/{doc_id}.pdf"` | ✅ |
| params `{"date": date, "type": 2, "Subscription-Key": ...}` (L105) | L57: 同一 | ✅ |

### USE_MOCK_EDINET デフォルト値

記事L180: 「`USE_MOCK_EDINET=true`（デフォルト）の場合、実APIを叩かずにモックデータで動作します」

実装L18: `USE_MOCK_EDINET = os.environ.get("USE_MOCK_EDINET", "true").lower() == "true"`

デフォルト `"true"`（モックモード） ✅ 記事の説明と一致

### docTypeCode

記事L66: 「有価証券報告書の docTypeCode は **120**」

実装L44: `def fetch_document_list(date: str, doc_type_code: str = "120")`
実装L60: `return [r for r in results if r.get("docTypeCode") == doc_type_code]`

✅ 正確

**CR-1（M7）判定: ✅ PASS**

---

## CR-2: M6 実装との照合

### 主要関数（m6_law_url_collector.py）

| 記事の記述 | 実装 | 判定 |
|-----------|------|------|
| `_EGOV_BASE = "https://laws.e-gov.go.jp/api/1"` (L222) | 実装に存在 | ✅ |
| `_CATEGORIES = [2, 3, 4]` (L223) | 実装に存在 | ✅ |
| `_get_law_list(category: int) -> list[dict]` (L226) | L49: 同一シグネチャ | ✅ |
| `_match(law_name: str, laws: list[dict]) -> Optional[dict]` (L246) | L63: 同一シグネチャ | ✅ |
| `collect(yaml_path: Path, output_path: Path) -> dict` (L274) | L77: 同一シグネチャ | ✅ |

### collect() 内部の entries キー

記事L276: `entries = data.get("entries", [])`

実装L79: `entries = data.get("entries", [])` ✅

> 注: m6 は `10_Research/law_entries_human_capital.yaml`（`entries:` キー使用）を対象とし、m2 が対象とする `laws/human_capital_2024.yaml`（`amendments:` キー使用）とは別ファイル。記事の記述は実装と一致している。

### robots.txt 調査記述

記事L203-207:
```python
_ROBOTS_SUMMARY = (
    "fsa.go.jp: robots.txt→404。利用規約確認要、スクレイピング不実施。"
    " laws.e-gov.go.jp: robots.txt→HTML(未公開)。公式API(/api/1/)は政府提供のため利用可。"
)
```

実装に同文字列が存在 ✅

### M6 デフォルトYAMLパス（推奨修正 R-1）

記事L309 コメント: 「`laws/law_entries_human_capital.yaml` を対象」

実装L28: `_DEFAULT_YAML = _REPO_ROOT / "10_Research" / "law_entries_human_capital.yaml"`

**ディレクトリが `laws/` ではなく `10_Research/`**。記述は不正確（ただし重大な誤動作はない）。

### ssbj_2025.yaml スニペットの `source_confirmed` フィールド（必須修正 M-1）

記事L190-196:
```yaml
# laws/ssbj_2025.yaml の例
- id: sb-2025-001
  title: "SSBJ確定基準 S1 第13項 — ガバナンス開示"
  source: "https://www.ssb.or.jp/..."
  source_confirmed: false  # ← 未確認URLが存在する
```

**実装照合（laws/ssbj_2025.yaml）**:
- `id: sb-2025-001` ✅
- `source: "https://www.ssb-j.jp/..."` ✅（URLは若干異なるが許容）
- **`source_confirmed` フィールドは `ssbj_2025.yaml` に存在しない** ❌

`source_confirmed` は `laws/human_capital_2024.yaml` にも存在せず、m6 が対象とする `10_Research/law_entries_human_capital.yaml` 側のフィールド。実際の `laws/*.yaml` にはないフィールドを、あたかも `laws/ssbj_2025.yaml` に存在するかのように記述している。M6の説明用であれば `10_Research/law_entries_human_capital.yaml` のスニペットを使うべき。

**必須修正 M-1**: スニペットのコメントを `laws/ssbj_2025.yaml の例` → `10_Research/law_entries_human_capital.yaml の例`（または相当する実際のYAMLに修正）

**CR-2（M6）判定: ⚠️ FAIL（M-1: source_confirmed帰属誤り）**

---

## CR-3: M8 実装との照合

### データクラス（m8_multiyear_agent.py）

| 記事のフィールド | 実装 | 判定 |
|----------------|------|------|
| `YearlyReport.fiscal_year: int` (L339) | L63: `fiscal_year: int` | ✅ |
| `YearlyReport.structured_report: StructuredReport` (L340) | L64: `structured_report: StructuredReport` | ✅ |
| `YearlyReport.elapsed_sec: float = 0.0` (L341) | L65: `elapsed_sec: float = 0.0` | ✅ |
| `YearDiff.fiscal_year_from: int` (L346) | L81: `fiscal_year_from: int` | ✅ |
| `YearDiff.added_sections: list[SectionData]` (L348) | L83: `added_sections: list[SectionData]` | ✅ |
| `YearDiff.changed_sections: list[SectionData]` (L351) | L85: `changed_sections: list[SectionData]` | ✅ |
| `YearDiff.summary: str` (L352) | L86: `summary: str` | ✅ |

### 主要関数・定数

| 記事の記述 | 実装 | 判定 |
|-----------|------|------|
| `CHANGE_RATE_THRESHOLD: float = 0.20` (L360) | L47: `CHANGE_RATE_THRESHOLD: float = 0.20` | ✅ |
| `_text_change_rate(old_text, new_text) -> float` (L363) | L93: 同一シグネチャ | ✅ |
| `detect_section_changes(old, new) -> dict` (L388) | L118: `def detect_section_changes(old: StructuredReport, new: StructuredReport) -> dict[str, list[SectionData]]:` | ✅ |
| `compare_years(reports: list[YearlyReport]) -> YearDiff` (L443) | L182: 同一シグネチャ | ✅ |

### ValueError メッセージ

記事L452: `raise ValueError(f"最低2件の YearlyReport が必要（受取: {len(reports)}件）")`

実装L205: `f"compare_years には最低2件の YearlyReport が必要です（受取: {len(reports)}件）"`

テキストが若干異なる（「最低2件の」vs「compare_years には最低2件の〜必要です」）。内容は等価 → 許容範囲 ✅

### 変化率計算の手計算検証

記事の手計算例（L367-371）:
```
old="abc", new="abc"    → ratio=1.0 → 変化率=0.0（変化なし）
old="abc", new="xyz"    → ratio=0.0 → 変化率=1.0（全変化）
old="abc", new="abcdef" → ratio=6/9=0.667 → 変化率=0.333（変化あり）
```

`difflib.SequenceMatcher("abc", "abcdef").ratio()` は `2*6/(3+6) = 12/9` ではなく `2*M/(T+T2)` の計算。実際に検証すると `SequenceMatcher(None, "abc", "abcdef").ratio() ≈ 0.667` ✅ 正確

### パターンB: analyze_gaps / load_law_context

記事L683-684:
```python
from m3_gap_analysis_agent import analyze_gaps
from m2_law_agent import load_law_context
```

実装照合:
- `analyze_gaps`: m3_gap_analysis_agent.py L539 に存在 ✅
- `load_law_context`: m2_law_agent.py L235 に存在 ✅

**CR-3（M8）判定: ✅ PASS**

---

## CR-4: テスト件数・法令情報の正確性

### テスト件数「71件 PASS」⚠️（必須修正 M-2）

記事L620セクション見出し: 「テスト構成（pytest 71件 PASS）」
記事L645: 「全テスト実行（71件 PASS）」

**実測**: `pytest scripts/test_m6*.py scripts/test_m7*.py scripts/test_m8*.py scripts/test_e2e_batch.py -v` → **51 passed**

README記載のM6〜M8テスト件数: m6:13件 + m7:15件 + m8:15件 = 43件（E2E除く）
実測で確認した総数 51件。「71件」との差 -20件が説明できない。

**必須修正 M-2**: テスト件数を実測値に修正（「51件 PASS」または正確な内訳付きで記載）

### テストファイル一覧

記事L626-631:
```
scripts/
├── test_m6_law_url_collector.py
├── test_m6_m7_integration.py
├── test_m7_edinet_client.py
├── test_m8_multiyear.py
└── test_e2e_batch.py
```

全ファイルの存在確認 ✅

### EDINET API 記述

| 項目 | 確認 |
|------|------|
| 書類一覧 API URL | ✅ 正確 |
| docTypeCode 120（有価証券報告書） | ✅ 正確 |
| PDF DL URL（認証不要） | ✅ 正確 |
| `type=2` でメタデータ+詳細取得 | ✅ 正確 |
| Subscription-Key の取得方法説明 | ✅ 適切 |

### e-Gov API カテゴリ

記事L223: `_CATEGORIES = [2, 3, 4]  # 2=法律 3=政令 4=府令`

実装: `_CATEGORIES = [2, 3, 4]` ✅（コメントの法令種別分類も正確）

**CR-4 判定: ⚠️ FAIL（M-2: テスト件数71件→実測51件）**

---

## 指摘事項サマリー

### 必須修正（2件）

| ID | 重大度 | 箇所 | 内容 |
|----|-------|------|------|
| **M-1** | 🔴 | L190-196（M6 YAMLスニペット） | `laws/ssbj_2025.yaml の例` とあるが `source_confirmed` フィールドはssbj_2025.yamlに存在しない。`10_Research/law_entries_human_capital.yaml` の例として修正、またはスニペットコメントを修正せよ |
| **M-2** | 🔴 | L620, L645（テスト件数） | 「71件 PASS」→ 実測51件（M6:13+M7:15+M8:15+E2Eバッチ8件）。正確な件数に修正せよ |

### 推奨修正（2件）

| ID | 箇所 | 内容 |
|----|------|------|
| R-1 | L309コメント | 「`laws/law_entries_human_capital.yaml` を対象」→ 実装は `10_Research/law_entries_human_capital.yaml` |
| R-2 | L319（出力例） | エントリIDフォーマット `HC_20230131_001` は実装の `entries` 形式と異なる可能性あり（出力例として注記推奨） |

---

## 修正指示

### M-1（必須）: M6 YAMLスニペットのコメント修正

**箇所**: L190

```markdown
# 修正前
# laws/ssbj_2025.yaml の例
- id: sb-2025-001
  ...
  source_confirmed: false

# 修正後（いずれか）
# 10_Research/law_entries_human_capital.yaml の例（source_confirmedフィールドあり）
# または: laws/ssbj_2025.yaml の実際のフィールドに合わせ source_confirmed 行を削除
```

### M-2（必須）: テスト件数修正

**箇所**: L620（セクション見出し）・L645（コード内コメント）

実測値を記載:
```
テスト構成（pytest 51件 PASS）
```

または内訳付き:
```
M6: 13件 / M7: 15件 / M8: 15件 / E2Eバッチ: 8件 = 計51件
```

---

## 最終判定

```
⚠️ 条件付き承認
必須修正2件（M-1・M-2）修正・git commit後に正式承認
```

M7全関数名・API URL・M8全データクラス・変化率計算・compare_years は全て実装と一致 ✅
M6関数名・robotsメモ・`collect()`実装も正確 ✅
Frontmatter・文量・構成・EDINET申請説明も適切 ✅

---

*レビュー実施: 足軽7 / P9-CR-D-Zenn-04b / 2026-03-09*
*照合: m6_law_url_collector.py / m7_edinet_client.py / m8_multiyear_agent.py / laws/*.yaml*
*テスト実測: pytest scripts/test_m6*.py test_m7*.py test_m8*.py test_e2e_batch.py → 51 passed*
