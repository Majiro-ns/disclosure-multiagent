# P9クロスレビューレポート: P9-CR-D-EDINET-01

| 項目 | 内容 |
|---|---|
| レビューID | P9-CR-D-EDINET-01 |
| 対象タスク | D-EDINET-01（足軽7実装: EDINET API連携強化・バッチ分析版） |
| 対象コミット | eaeba21 |
| 対象ファイル | `scripts/m7_edinet_client.py` |
| レビュー実施 | 足軽8 |
| レビュー日時 | 2026-03-10 |
| 最終判定 | ⚠️ **条件付き承認**（必須修正1件） |

---

## 総評

足軽7の EDINET API連携強化実装（D-EDINET-01）を P9基準でクロスレビューした。
**USE_MOCK_EDINET=true にて TC-16〜22 の7件全PASS を実測確認**。
CR-1（DOS対策）・CR-2（BatchCompanyResult）・CR-4（CLI --batch）はいずれも正確に実装されている。
ただし、**TC-11 が環境依存で FAIL する問題**（`10_Research/samples/company_a.pdf` 未存在）が確認されたため、条件付き承認とする。

---

## テスト実行結果（実測）

```
$ cd scripts && USE_MOCK_EDINET=true python3 -m pytest test_m7_edinet_client.py -v
22 items collected

TC-1  validate_edinetcode 正常値           PASSED
TC-2  validate_edinetcode Eなし            PASSED
TC-3  validate_edinetcode 桁数不足         PASSED
TC-4  validate_edinetcode 余分な文字       PASSED
TC-5  validate_doc_id 正常値              PASSED
TC-6  validate_doc_id 先頭文字不正        PASSED
TC-7  validate_doc_id 長さ不正            PASSED
TC-8  fetch_document_list モック120       PASSED
TC-9  fetch_document_list 別種別→空       PASSED
TC-10 fetch_document_list 実API・キーなし  PASSED
TC-11 download_pdf モック既存PDF ★        FAILED ← 必須修正
TC-12 download_pdf 不正 doc_id            PASSED
TC-13 search_by_company 部分一致          PASSED
TC-14 search_by_company 一致なし          PASSED
TC-15 MOCK_DOCUMENTS 構造確認            PASSED
TC-16 REQUEST_DELAY >= 3.0              PASSED ✅
TC-17 BatchCompanyResult フィールド      PASSED ✅
TC-18 batch_fetch_companies 3社全ヒット   PASSED ✅
TC-19 batch_fetch_companies 混在         PASSED ✅
TC-20 batch_fetch_companies 空リスト     PASSED ✅
TC-21 batch_fetch_companies 入力順保持   PASSED ✅
TC-22 batch_fetch_companies year確認     PASSED ✅

結果: 21 passed, 1 failed
```

---

## CR-1: DOS対策確認

### REQUEST_DELAY 定数定義

```python
# L27: 正確に定義されている
REQUEST_DELAY: float = 3.0  # ✅ 3.0秒以上
```

**判定: ✅ PASS**（TC-16も PASS 確認）

### sleep 処理の実装確認

| 関数 | モック時 | 実API時 | 判定 |
|---|---|---|---|
| `download_pdf` | sleep なし（L94-98 のモック分岐でreturn） | `time.sleep(REQUEST_DELAY)` (L100) | ✅ |
| `search_by_company` | sleep なし（L117-118 のモック分岐でreturn） | `time.sleep(REQUEST_DELAY)` (L125) | ✅ |
| `batch_fetch_companies` | skip（`i > 0 and not USE_MOCK_EDINET` L148） | `time.sleep(request_delay)` (L149) | ✅ |

**全関数でモック時はsleepをスキップしている。DOS対策要件を完全に満たす。**

---

## CR-2: BatchCompanyResult 検証

### dataclass フィールド実装確認

```python
@dataclass
class BatchCompanyResult:
    company_name: str         ✅
    year: int                 ✅
    docs: list[dict]          ✅ (field(default_factory=list))
    downloaded_paths: list[str] ✅ (field(default_factory=list))
    elapsed_sec: float        ✅ (= 0.0)
    error: str                ✅ (= "")

    @property
    def success(self) -> bool:
        return not self.error and len(self.docs) > 0  ✅
```

**タスク仕様の全フィールドが実装されている。**

### success プロパティのロジック確認

| 状態 | expected | 実測 |
|---|---|---|
| docs >= 1 かつ error="" | True | ✅ True |
| docs = 0、error="" | False | ✅ False |
| docs >= 1 かつ error あり | False | ✅ False |

**判定: ✅ PASS**（TC-17で実測確認済み）

### エラーハンドリング

```python
# L173-179: 例外捕捉してerrorフィールドに格納
except Exception as exc:
    results.append(BatchCompanyResult(
        company_name=company_name,
        year=year,
        elapsed_sec=time.time() - start,
        error=str(exc),   # ← 適切
    ))
```

**判定: ✅ 適切**（TC-19で0件・エラーなし=⚠️ の区別も正確）

---

## CR-3: batch_fetch_companies 実行確認

### TC-16〜22 実測（全7件）

| TC | 内容 | 結果 |
|---|---|---|
| TC-16 | REQUEST_DELAY >= 3.0 | ✅ PASS |
| TC-17 | BatchCompanyResult フィールド・success | ✅ PASS |
| TC-18 | 3社全ヒット | ✅ PASS |
| TC-19 | ヒットあり・なし混在 | ✅ PASS |
| TC-20 | 空リスト入力→空リスト | ✅ PASS |
| TC-21 | 入力順保持 | ✅ PASS |
| TC-22 | year フィールド確認 | ✅ PASS |

**TC-16〜22: 7件全PASS（実測）**

### 全体テスト回帰確認

M7以外の既存テスト群（M6/M8/E2E等）は test_api_router.py/test_auth.py/test_checklist.py の3ファイルが FastAPI/Pydantic バージョン不整合で collection error。これは D-EDINET-01 実装とは無関係の既存問題。M7テスト自体の回帰: 21/22 PASS（TC-11のみ環境依存FAIL）。

---

## CR-4: CLI --batch オプション確認

### 引数定義（実コード L190-193）

```python
parser.add_argument(
    "--batch",
    help='バッチ処理JSON: {"companies":[{"company_name":"...","year":2023},...]}',
)
```

**ヘルプ表示実測**:
```
options:
  --batch BATCH  バッチ処理JSON:
                 {"companies":[{"company_name":"...","year":2023},...]}
```

**判定: ✅ 引数定義・ヘルプ表示ともに正確**

### CLI 実動作確認（USE_MOCK_EDINET=true）

```bash
$ USE_MOCK_EDINET=true python3 m7_edinet_client.py \
    --batch '{"companies":[{"company_name":"サンプル社A","year":2023},{"company_name":"存在しない会社","year":2023}]}'

[M7] EDINET クライアント起動（モード: モック）
[M7] バッチ処理開始: 2 社
  ✅ サンプル社A(2023): 1件取得 DL=0 (0.0s)
  ⚠️ 存在しない会社(2023): 0件取得 DL=0 (0.0s)
```

**判定: ✅ 正常動作確認**（ヒット/未ヒット両方の表示も正確）

---

## CR-5: 総合判定

### ⚠️ 必須修正（1件）

**[MUST-1] TC-11: サンプルPDF依存の環境脆弱性**

| 項目 | 内容 |
|---|---|
| テスト | `test_tc11_download_pdf_mock_returns_existing_file` |
| 失敗内容 | `FileNotFoundError: 10_Research/samples/company_a.pdf が見つかりません` |
| 根本原因 | `10_Research/samples/` ディレクトリが空（company_a.pdf 未存在） |
| 影響範囲 | CI環境・クリーンclone環境で必ずFAIL |
| 修正方針 | A案: `tmp_path` フィクスチャで一時PDFを動的作成してモックする |
|  | B案: `samples/` にダミーPDFをgit追跡で追加する |
| 推奨 | A案（テスト内で自己完結。環境依存を排除） |

**修正案A（推奨）**:
```python
def test_tc11_download_pdf_mock_returns_existing_file(tmp_path, monkeypatch):
    """モック: 存在するPDFのパスを返す（tmp_pathで自己完結）"""
    # サンプルPDFを一時ディレクトリに作成してモック
    fake_pdf = tmp_path / "company_a.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    import m7_edinet_client as m7
    monkeypatch.setattr(m7, "_SAMPLES_DIR", tmp_path)

    path = m7.download_pdf("S100A001", str(tmp_path / "output"))
    assert path.endswith(".pdf")
    assert os.path.exists(path)
```

### 問題なし（指摘なし）

| CR項目 | 判定 |
|---|---|
| CR-1: REQUEST_DELAY=3.0 定義 | ✅ |
| CR-1: モック時sleep省略 | ✅ |
| CR-2: BatchCompanyResult 全フィールド | ✅ |
| CR-2: success プロパティロジック | ✅ |
| CR-2: エラーハンドリング | ✅ |
| CR-3: TC-16〜22 全件PASS | ✅ |
| CR-4: --batch 引数定義 | ✅ |
| CR-4: ヘルプ表示 | ✅ |
| CR-4: CLI実動作 | ✅ |

### 最終判定

```
⚠️ 条件付き承認

必須修正: MUST-1（TC-11 テスト修正）
修正後: 再テスト実行し 22 passed を確認してから merge すること
推奨修正: なし（設計・実装は高品質）
```

---

*P9-CR-D-EDINET-01 レビュー完了 — 足軽8*
