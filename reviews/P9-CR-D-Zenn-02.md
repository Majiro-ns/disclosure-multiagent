# P9-CR-D-Zenn-02: Phase2 Zenn記事 クロスレビュー

| 項目 | 内容 |
|---|---|
| レビューID | P9-CR-D-Zenn-02 |
| 対象タスク | D-Zenn-02（Phase2記事） |
| 対象ファイル | `docs/article_disclosure_phase2_draft.md`（23,755byte） |
| 照合対象 | `scripts/m6_law_url_collector.py` / `scripts/m7_edinet_client.py` / `scripts/m8_multiyear_agent.py` / `articles/zenn_disclosure_phase2.md` |
| レビュー実施 | 足軽8 |
| 実施日 | 2026-03-09 |
| 最終判定 | ⚠️ **条件付き承認（必須修正2件）** |

---

## 総評

Phase2 の技術的発見（EDINET直接DL認証不要・e-Gov API連携）を正確に説明した良質な記事。
M6・M7の実装との照合は概ね正確。ただし **M8のコードスニペットに2件の実装乖離** があり、
読者がコピペ実行するとエラーになる。必須修正2件の対応後に正式承認。

---

## CR-1: コードスニペット vs 実装照合

### M6（`m6_law_url_collector.py`）

| スニペット箇所 | 記事内容 | 実装 | 判定 |
|---|---|---|---|
| `_EGOV_BASE` (L213) | `"https://laws.e-gov.go.jp/api/1"` | m6 L30: 同一 | ✅ |
| `_CATEGORIES` (L214) | `[2, 3, 4]` | m6 L32: 同一 | ✅ |
| `_get_law_list()` (L216-228) | 実装と一致 | m6 L49-60: 同一 | ✅ |
| `_match()` (L237-248) | 完全一致 | m6 L63-74: 同一 | ✅ |
| JSON `"source"` (L269) | `"e-Gov API"` | `"e-Gov API lawlists"` | △軽微 |
| JSON `"note"` (L271) | 簡略説明 | より詳細な文言 | △軽微 |
| 3段階 confidence 説明 (L252-255) | high/medium/low 定義正確 | m6 L66-73: 一致 | ✅ |

**M6 判定**: ✅ 本質的な実装内容は正確。JSON例のフィールド値差異は説明上の省略として許容範囲。

---

### M7（`m7_edinet_client.py`）

| スニペット箇所 | 記事内容 | 実装 | 判定 |
|---|---|---|---|
| `USE_MOCK_EDINET` デフォルト (L77) | `"true"` | m7 L18: `"true"` | ✅ |
| `EDINET_DL_BASE` (L116) | `"https://disclosure2dl.edinet-fsa.go.jp/searchdocument/pdf"` | m7 L15: 同一 | ✅ |
| `EDINET_API_BASE` (L78) | `"https://api.edinet-fsa.go.jp/api/v2"` | m7 L16: 同一 | ✅ |
| `fetch_document_list()` (L86-101) | 実装と実質一致 | m7 L44-62: 一致 | ✅ |
| `download_pdf()` (L118-141) | 実装と完全一致 | m7 L65-88: 同一 | ✅ |
| `validate_doc_id()` (L149-151) | `r"S[A-Z0-9]{7}"` | m7 L41: 同一 | ✅ |
| `search_by_company()` (L161-174) | 実装と完全一致 | m7 L91-104: 同一 | ✅ |
| モック出力例 (L188-193) | 3件・フォーマット正確 | MOCK_DOCUMENTS 3件と一致 | ✅ |

**M7 判定**: ✅ 全スニペット正確。

---

### M8（`m8_multiyear_agent.py`）

| スニペット箇所 | 記事内容 | 実装 | 判定 |
|---|---|---|---|
| `CHANGE_RATE_THRESHOLD` (L306) | `0.20` | m8 L47: `0.20` | ✅ |
| `YearlyReport` dataclass (L287-289) | 3フィールド一致 | m8 L54-65: 同一 | ✅ |
| `YearDiff` dataclass (L291-300) | 6フィールド（型は省略） | m8 L68-86: フィールド一致 | ✅ |
| **変化率計算関数名 (L308)** | **`_calc_change_rate(text_a, text_b)`** | **m8 L93: `_text_change_rate(old_text, new_text)`** | **❌ 要修正** |
| 変化率ロジック (L309-313) | `not text_a and not text_b → 0.0` | 同 + `not old_text or not new_text → 1.0` | △片方空省略 |
| **`compare_years()` 呼び出し (L326)** | **`compare_years(yearly_2023, yearly_2024)`（2引数）** | **m8 L182: `compare_years(reports: list[YearlyReport])`（リスト1引数）** | **❌ 要修正** |

---

## CR-2: 関数シグネチャ確認

### ❌ M1（必須修正）: `m8_multiyear_agent.py` 変化率計算関数名不一致

**記事 L308-313（現在）:**
```python
CHANGE_RATE_THRESHOLD: float = 0.20  # 本文変化率 > 20% → changed

def _calc_change_rate(text_a: str, text_b: str) -> float:
    """difflib.SequenceMatcher で変化率を計算（0.0〜1.0）"""
    if not text_a and not text_b:
        return 0.0
    matcher = difflib.SequenceMatcher(None, text_a, text_b)
    return 1.0 - matcher.ratio()
```

**実装 m8 L93-111（実際）:**
```python
def _text_change_rate(old_text: str, new_text: str) -> float:
    """2つのテキストの変化率を計算する（0.0〜1.0）"""
    if not old_text and not new_text:
        return 0.0
    if not old_text or not new_text:   # ← 記事に未記載のエッジケース処理
        return 1.0
    ratio = difflib.SequenceMatcher(None, old_text, new_text).ratio()
    return 1.0 - ratio
```

**差異3点**:
1. **関数名**: `_calc_change_rate` → 実際は `_text_change_rate`
2. **引数名**: `text_a, text_b` → 実際は `old_text, new_text`
3. **エッジケース処理**: 片方空の場合に `return 1.0` が省略されている

**修正案（記事 L308）:**
```python
def _text_change_rate(old_text: str, new_text: str) -> float:
    """difflib.SequenceMatcher で変化率を計算（0.0〜1.0）"""
    if not old_text and not new_text:
        return 0.0
    if not old_text or not new_text:
        return 1.0  # 片方が空なら完全変化
    matcher = difflib.SequenceMatcher(None, old_text, new_text)
    return 1.0 - matcher.ratio()
```

---

### ❌ M2（必須修正）: `compare_years()` 呼び出しシグネチャ不一致

**記事 L325-327（現在）:**
```python
from m8_multiyear_agent import compare_years

# 2023年度 vs 2024年度 の比較
diff = compare_years(yearly_2023, yearly_2024)   # ← 2引数呼び出し
```

**実装 m8 L182（実際のシグネチャ）:**
```python
def compare_years(reports: list[YearlyReport]) -> YearDiff:
    """複数年度のレポートを比較し、最新2年度間の差分を返す"""
```

**問題**: `compare_years(yearly_2023, yearly_2024)` は2引数だが、実装はリスト1引数。
読者がそのまま実行すると `TypeError: compare_years() takes 1 positional argument but 2 were given` が発生する。

**修正案（記事 L326）:**
```python
# 2023年度 vs 2024年度 の比較（リストで渡す）
diff = compare_years([yearly_2023, yearly_2024])
```

---

## CR-3: テスト件数確認

### 記事 vs articles/zenn_disclosure_phase2.md の一致確認

| テストファイル | 記事(draft) | zenn記事 | 一致 |
|---|---|---|---|
| test_m1_pdf_agent.py | 29件 | 29件 | ✅ |
| test_m2_law_agent.py | 19件 | 19件 | ✅ |
| test_m3_gap_analysis.py | 16件 | 16件 | ✅ |
| test_m4_proposal.py | 41件 | 41件 | ✅ |
| test_m5_report.py | 37件 | 37件 | ✅ |
| test_e2e_pipeline.py | 22件 | 22件 | ✅ |
| test_m6_law_url_collector.py | 13件 | 13件 | ✅ |
| test_m7_edinet_client.py | 15件 | 15件 | ✅ |
| test_m6_m7_integration.py | 15件 | 15件 | ✅ |
| **合計** | **207件** | **207件** | ✅ |

両記事の件数は完全一致。Phase2完了時点の値として正確。

**N3（情報鮮度）**: Phase2以降に追加された機能（shoshu/SSBJ/銀行業等）でテスト数が増加し現在318+件。Phase2記事として207件は正確だが、記事公開時に `※ Phase3以降のモジュール追加でテスト数は増加` の注記があると親切。

---

## CR-4: 環境変数・設定値確認

| 設定項目 | 記事値 | 実装値 | 判定 |
|---|---|---|---|
| `USE_MOCK_EDINET` デフォルト | `"true"` | m7 L18: `"true"` | ✅ |
| `EDINET_SUBSCRIPTION_KEY` | 環境変数設定 | m7 L19: 一致 | ✅ |
| `EDINET_DL_BASE` URL | `https://disclosure2dl.edinet-fsa.go.jp/searchdocument/pdf` | m7 L15: 同一 | ✅ |
| `EDINET_API_BASE` URL | `https://api.edinet-fsa.go.jp/api/v2` | m7 L16: 同一 | ✅ |
| `CHANGE_RATE_THRESHOLD` | `0.20` | m8 L47: `0.20` | ✅ |
| `RUN_NETWORK_TESTS` デフォルト | `"false"` (スキップ) | テスト実装と一致 | ✅ |
| `USE_MOCK_LLM` 言及 (L74) | M3と同様設計 | 実装一致 | ✅ |

**CR-4 判定**: ✅ 全設定値正確。

---

## CR-5: 技術的事実確認

| 事実 | 記事内容 | 実際 | 判定 |
|---|---|---|---|
| EDINET 書類一覧API URL | `api.edinet-fsa.go.jp/api/v2/documents.json` | m7 L16と一致 | ✅ |
| EDINET PDF直接DL URL | `disclosure2dl.edinet-fsa.go.jp/searchdocument/pdf/{docID}.pdf` | m7 L15と一致 | ✅ |
| PDF直接DL認証 | 認証不要 | m7 実装・docstringと一致 | ✅ |
| e-Gov API BASE | `https://laws.e-gov.go.jp/api/1` | m6 L30と一致 | ✅ |
| カテゴリ 2=法律/3=政令/4=府令 | 記事L230 | m6 L32と一致 | ✅ |
| 書類管理番号形式 | `S + 7桁英数字` | `r"S[A-Z0-9]{7}"` | ✅ |
| docTypeCode 120 = 有報 | 記事 L104-111 | m7 MOCK_DOCUMENTS一致 | ✅ |
| fsa.go.jp robots.txt | `404` | m6 docstring L12と一致 | ✅ |
| e-Gov API 認証不要 | 記載あり | m6 L16と一致 | ✅ |
| `stream=True` でメモリ効率 | 記事L144説明 | m7 L77と一致 | ✅ |

**CR-5 判定**: ✅ 全技術的事実正確。

---

## 指摘事項サマリー

| ID | 種別 | 重大度 | 内容 | 場所 |
|---|---|---|---|---|
| M1 | **必須修正** | 🔴 高 | `_calc_change_rate(text_a, text_b)` → 実装は `_text_change_rate(old_text, new_text)`。コピペでエラー | 記事 L308 |
| M2 | **必須修正** | 🔴 高 | `compare_years(yearly_2023, yearly_2024)` → 実装はリスト1引数。TypeError発生 | 記事 L326 |
| N1 | 情報的 | ⚪ 低 | JSON出力の `"source"`: `"e-Gov API"` → 実装は `"e-Gov API lawlists"` | 記事 L269 |
| N2 | 情報的 | ⚪ 低 | JSON出力の `"note"` 文言が実装と異なる（概略説明） | 記事 L271 |
| N3 | 情報的 | ⚪ 低 | テスト件数207件はPhase2時点の値。現在318+件 | 記事 L493 |
| N4 | 情報的 | ⚪ 低 | `_text_change_rate` の片方空→1.0のエッジケース処理が省略 | 記事 L309-313 |

**必須修正: 2件（M1・M2）/ 推奨修正: 0件 / 情報的: 4件**

---

## 最終判定

```
⚠️ 条件付き承認
必須修正2件（M1・M2）を修正後、正式承認（再CR不要）
M6・M7・統合テスト説明は正確であり、記事品質は高い
```

M6・M7の実装照合は完全に正確。技術的事実・環境変数・URLも正確。
M8のコードスニペット2箇所（L308関数名・L326呼び出し方）のみ要修正。

---

*P9-CR-D-Zenn-02 実施: 足軽8 / 2026-03-09*
