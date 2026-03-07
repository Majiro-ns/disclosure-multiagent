# EDINET から有価証券報告書（有報）PDFを取得する方法

> 有報PDFは**無料**で取得できます。EDINETは金融庁が運営する電子開示システムです。

---

## 方法1: EDINET Web サイトから手動ダウンロード（最も簡単）

### 手順

1. **EDINETにアクセス**
   - URL: https://disclosure2.edinet-fsa.go.jp/

2. **書類検索を開く**
   - トップページ右上の「書類検索」をクリック

3. **会社名または証券コードで検索**
   - 例: 「トヨタ自動車」「7203」

4. **書類種別を「有価証券報告書」に絞り込む**
   - 書類種別ドロップダウン → 「有価証券報告書」を選択

5. **対象年度の書類を選択**
   - 提出日・事業年度を確認して対象を選ぶ

6. **「書類」列のリンクをクリック → PDFアイコンをクリックしてダウンロード**

### スクリーンショット付き詳細手順（参考）

```
トップページ
  └─ 「書類検索」タブ
      └─ 会社名: "トヨタ自動車" を入力 → 検索
          └─ 書類種別: "有価証券報告書" で絞り込み
              └─ 2024年度提出 を選択
                  └─ 書類リスト → 有価証券報告書 → PDF ダウンロード
```

---

## 方法2: M7 EDINET クライアント（本ツールの自動取得機能）

本ツールには EDINET 連携クライアント（`m7_edinet_client.py`）が含まれており、**Subscription-Key なし**で最新の有報PDFを自動ダウンロードできます。

```python
import sys
sys.path.insert(0, "scripts/")

from m7_edinet_client import EdinetClient

client = EdinetClient()

# 企業コード（EDINETコード）を指定してダウンロード
# EDINETコード一覧: https://disclosure2.edinet-fsa.go.jp/WZEK0010.aspx
pdf_path = client.download_latest_yuho("E02142")  # トヨタ自動車
print(f"Downloaded: {pdf_path}")
```

### EDINETコードの調べ方

1. EDINET トップ → 「コード検索」
2. 会社名を入力 → EDINETコード（E から始まる6桁）を確認

主要企業のEDINETコード例:

| 会社名 | EDINETコード | 証券コード |
|-------|-------------|-----------|
| トヨタ自動車 | E02142 | 7203 |
| ソニーグループ | E01777 | 6758 |
| NTT | E04425 | 9432 |
| 三菱UFJフィナンシャル | E03606 | 8306 |
| ファーストリテイリング | E03277 | 9983 |

---

## 方法3: EDINET API（Subscription-Key 必要）

より高度な書類検索・一括取得には EDINET の API（Subscription-Key 版）が利用できます。

### Subscription-Key の取得方法

1. EDINET API 利用申請ページにアクセス
   - URL: https://disclosure2.edinet-fsa.go.jp/WZEK0010.aspx
2. 「API利用申請」から申請フォームを送信
3. 審査後（数日〜1週間）にメールで Subscription-Key が届く

### API 利用例

```python
import os
import sys
sys.path.insert(0, "scripts/")

from m7_edinet_client import EdinetClient

# Subscription-Key を設定
os.environ["EDINET_SUBSCRIPTION_KEY"] = "your-key-here"

client = EdinetClient()

# 日付を指定して書類一覧を取得
docs = client.list_documents(date="2025-03-31", doc_type="120")  # 120 = 有価証券報告書

for doc in docs:
    print(f"{doc['filerName']} ({doc['edinetCode']}): {doc['docDescription']}")
    pdf_path = client.download_pdf(doc["docID"])
    print(f"  → Downloaded: {pdf_path}")
```

### 主な EDINET API エンドポイント

| エンドポイント | 説明 |
|-------------|------|
| `GET /api/v2/documents.json?date=YYYY-MM-DD&type=2` | 指定日の書類一覧 |
| `GET /api/v2/documents/{docID}?type=1` | 書類ZIP（メタデータ+本文） |
| `GET /api/v2/documents/{docID}?type=4` | PDFのみ |

---

## 書類種別コード（type / 書類種別）

EDINET 書類検索・API 共通の書類種別コード:

| コード | 書類種別 |
|-------|---------|
| `120` | 有価証券報告書 |
| `140` | 半期報告書 |
| `160` | 四半期報告書 |
| `130` | 内部統制報告書 |
| `350` | 株主総会招集通知（参考書類等） |

---

## よくある質問

### Q: 有報PDFに「閲覧用」と「XBRL」の両方がある。どちらを使えばよい？

A: 本ツールは **PDFのみ** に対応しています。「閲覧用PDF」をダウンロードしてください。

### Q: EDINET の有報PDFはいつから取得できる？

A: 一般的に **提出日の翌営業日** から閲覧・ダウンロード可能です。最新の有報は3月期決算企業であれば6月末頃に提出されます。

### Q: 過去の有報も取得できる？

A: EDINET では **2004年以降** の書類が閲覧可能です。古い書類は PDF ではなく HTML 形式の場合があります。

### Q: 有報以外のファイルも分析できる？

A: `doc_type="shoshu"` を指定すると株主総会招集通知も分析できます。

```bash
USE_MOCK_LLM=true python3 run_e2e.py shoshu.pdf \
    --company-name "株式会社A" \
    --fiscal-year 2025 \
    --doc-type shoshu
```

---

## 関連リンク

- [EDINET（電子開示システム）](https://disclosure2.edinet-fsa.go.jp/)
- [EDINET API 仕様書（金融庁）](https://disclosure2.edinet-fsa.go.jp/WZEK0010.aspx)
- [有価証券報告書 提出期限カレンダー（金融庁）](https://www.fsa.go.jp/policy/kaijishishin/index.html)
- [SSBJ（サステナビリティ基準委員会）](https://www.ssb-j.jp/)

---

*このドキュメントの内容は 2024年時点のものです。EDINET の UI や API 仕様が変わった場合は PR でお知らせください。*
