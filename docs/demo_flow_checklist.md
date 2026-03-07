# disclosure-multiagent デモ動作確認チェックリスト

**確認日**: 2026-03-12
**確認者**: ashigaru7 (cmd_353k_2_a7b)
**対象**: GitHub Public化後の初回ユーザー体験（3/14 公開予定）

---

## 結論サマリー

| フロー | 判定 | 備考 |
|---|---|---|
| README → Quick Start (Layer 1 pip) | ✅ PASS | モックモード即動作、コード3行 |
| README → Quick Start (Layer 2 CLI) | ✅ PASS | `disclosure-check --help` 正常 |
| README → Quick Start (Layer 3 Docker) | ⚠️ 要注意 | 起動待機時間の案内を追加推奨 |
| /sample ページ（サンプル閲覧） | ✅ PASS | 初回ガイドカード・DLボタン・CTA完備 |
| /sample → PDF DL → トップへ戻りアップロード | ✅ PASS | ダウンロード→ドロップ→分析の流れ明確 |
| EDINET（M7） → CLI パイプライン | ✅ PASS | USE_MOCK_EDINET=true でネット不要 |

---

## 1. README → Layer 1（pip ライブラリ）

```bash
pip install disclosure-multiagent
```

```python
import os; os.environ.setdefault("USE_MOCK_LLM", "true")
from scripts.m1_pdf_agent import extract_report
report = extract_report("your_report.pdf")
print(report.company_name, "—", len(report.sections), "sections extracted")
```

**確認事項**:
- [x] `USE_MOCK_LLM=true` がデフォルトで APIキー不要と明記 ✅
- [x] コメントに `# Minimum working example — copy and paste as-is` と記載 ✅
- [x] フルパイプライン（M1→M5）のサンプルコードも掲載 ✅

**潜在的ハードル**: なし（モックモードが完全動作）

---

## 2. README → Layer 2（CLI）

```bash
disclosure-check your_report.pdf --level 竹
```

**確認事項**:
- [x] `disclosure-check --help` 正常動作確認済み（ashigaru3） ✅
- [x] モックモードがデフォルトで APIキー不要 ✅
- [x] レポート出力先パスが明示されている ✅

**潜在的ハードル**: なし

---

## 3. README → Layer 3（Docker）

```bash
git clone https://github.com/Majiro-ns/disclosure-multiagent.git
cd disclosure-multiagent
cp .env.example .env
docker-compose up --build
```

**確認事項**:
- [x] `.env.example` 存在・内容適切 ✅
- [x] `docker-compose.yml` が backend(8010) + web(3010) の2サービス構成 ✅
- [x] `depends_on: backend: condition: service_healthy` で起動順制御 ✅
- [x] README に v1/v2 両コマンドを記載 ✅

**⚠️ 潜在的ハードル: 起動待機時間**
- backend の `start_period: 15s` + web の `start_period: 30s` のため
  `docker-compose up` 後 約45秒はブラウザでアクセスできない
- README には「起動後すぐ開ける」とは書いていないが、明示もしていない
- **推奨**: README に `# Ready in ~30-60 seconds` 等の一言を追加

**URL 確認**:
- Web UI: http://localhost:3010 ✅
- サンプル: http://localhost:3010/sample ✅
- REST API: http://localhost:8010 ✅
- Swagger: http://localhost:8010/docs ✅

---

## 4. /sample ページ（サンプル閲覧）

http://localhost:3010/sample

**確認事項**:
- [x] サンプル注記バナー（架空企業明示）表示 ✅
- [x] 「今すぐ試してみよう」ガイドカード（3ステップ: DL→ドロップ→分析） ✅
- [x] `sample_yuho.pdf` ダウンロードボタン (`/sample_yuho.pdf`) ✅
- [x] CTAボタン: 「PDFアップロード」→ / (トップ) ✅
- [x] CTAボタン: 「証券コード検索」→ 同左 ✅
- [x] ギャップサマリーカード: 5件検出（has_gap=True）✅
- [x] 松竹梅提案カード: status="pass" でバッジ正常 ✅
- [x] 変更種別: "追加必須"/"修正推奨" でアイコン正常 ✅

**潜在的ハードル**: なし（前タスクで UI バグを修正済み）

---

## 5. /sample → PDF DL → アップロードフロー

1. /sample ページでサンプルPDFダウンロードボタンをクリック
2. `sample_yuho.pdf`（架空有報）をローカル保存
3. トップページ (/) でドラッグ＆ドロップまたはクリックでアップロード
4. M1→M5 パイプライン実行 → ギャップ分析結果表示

**確認事項**:
- [x] `sample_yuho.pdf` が `web/public/sample_yuho.pdf` に存在 ✅
- [x] DLボタンが `<a href="/sample_yuho.pdf" download>` で実装 ✅
- [x] トップページに PDF アップロード UI 存在（別タスク確認済み）✅

**潜在的ハードル**: モックモードで実行時はパイプラインが mock 結果を返すため、
  実際のPDF解析結果ではなくモックデータが表示される点を README に明示できると親切。
  ただし現状でも「USE_MOCK_LLM=true はデフォルト」と README に記載あり ✅

---

## 6. EDINET パイプライン（M7）

```bash
USE_MOCK_EDINET=true USE_MOCK_LLM=true python3 scripts/m7_edinet_client.py \
  --company "サンプル社" --year 2024
```

**確認事項**:
- [x] `USE_MOCK_EDINET=true` で API キー不要 ✅
- [x] モックドキュメントで動作確認可能 ✅
- [x] EDINET Subscription-Key 申請先リンクが README に記載 ✅

---

## 7. 発見した改善候補

### 優先度: 低（3/14公開後でも可）
| 項目 | 詳細 |
|---|---|
| Docker起動時間を README に追記 | `# Ready in ~30-60 seconds` 等1行追加 |
| モックモードと実分析の違いを明示 | サンプルアップロード時にモック結果が返る点のUX改善 |
| 他記事の「」除去 | banking(16件), batch(14件), pipeline(23件), shoshu(25件), ssbj(28件) ← Zenn公開前に要対応 |

### 優先度: 対応済み（このタスクで修正）
| 項目 | 修正内容 |
|---|---|
| edinet記事の法令件数誤り | 50件→30件、人的資本25件→8件/5件（適用） |
| edinet記事のfiscal_year | 2025→2024に変更（SSBJ適用確認のため） |

---

## 8. 殿操作が必要な残タスク（3/14公開前）

- [ ] **GitHub リポジトリを Private → Public に変更**（Settings > Danger Zone）
- [ ] **GitHub Release ページ作成**: releases/new → タグ v1.0.0 → RELEASE_NOTES_v1.0.0.md 貼り付け
- [ ] （任意）Zenn 記事の published: true 変更と投稿（oss_launch 記事から先行）

---

*このファイルは git 追跡対象。OSS 公開後は適宜更新可。*
