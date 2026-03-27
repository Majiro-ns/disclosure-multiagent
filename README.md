# disclosure-multiagent

[![CI](https://github.com/Majiro-ns/disclosure-multiagent/actions/workflows/test.yml/badge.svg)](https://github.com/Majiro-ns/disclosure-multiagent/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-747%20passing-brightgreen)](scripts/)
[![Mock Mode](https://img.shields.io/badge/mock%20mode-APIキー不要-orange)](docs/)

EDINETから有価証券報告書を取得し、Big4観点でAI開示チェックを行うOSSツール。

> 「**松の事例は国も教えてくれるが、竹や梅は決して教えてくれない。**」
>
> 100点（松）の開示事例は金融庁も教えてくれる。
> 60点（梅）で確実に法令を超える方法・80点（竹）の業界標準水準は、誰も教えてくれない。
> コンサルを呼ばなくても、自社の開示担当者が自力で改善点を把握できるツールを目指しています。

---

## できること（30秒）

```
有価証券報告書 PDF を入力
        ↓
① PDF読取   — 有報のセクションを自動抽出
        ↓
② 法令確認  — 最新の開示規制 YAML と照合
        ↓
③ ギャップ分析 — 「何が足りないか」を検出
        ↓
④ 改善提案  — 梅・竹・松 3段階の記載文案を生成
        ↓
⑤ レポート生成 — Markdown レポートとして出力
```

| 水準 | スコア | 説明 |
|------|--------|------|
| 梅 | 60点 | **法令準拠ライン** — これだけやれば監督官庁から指摘されない |
| 竹 | 80点 | **業界標準** — 同業他社と遜色ない水準 |
| 松 | 100点 | **先進開示** — 機関投資家から評価される水準 |

---

## 特徴

- **EDINET API 対応** — 有価証券報告書 PDF の一括自動取得（M7）
- **Big4 視点の開示チェックプロファイル** — KPMG / EY / PwC / Deloitte 各社のベスト・イン・クラス事例を YAML プロファイルとして収録
- **マルチエージェント構成（M1〜M9）** — PDF解析 → 法令照合 → ギャップ分析 → 松竹梅提案 → レポート出力 → Word/Excel エクスポートまで一貫
- **747テスト / `USE_MOCK_LLM=true` でAPIキー不要** — クローン直後に全テストを実行できる
- **A2A プロトコル対応** — 外部エージェントからの直接呼び出しが可能
- **法令 YAML 拡張可能** — `laws/` にファイルを追加するだけで新規規制を取り込める

---

## インストール

```bash
git clone https://github.com/Majiro-ns/disclosure-multiagent.git
cd disclosure-multiagent
pip install -e ".[dev]"
```

または Poetry を使用する場合:

```bash
poetry install
```

**最小限インストール（コアパイプラインのみ）:**

```bash
pip install pymupdf pyyaml
```

**本番LLM対応（Claude API）:**

```bash
pip install "disclosure-multiagent[llm]"
```

---

## クイックスタート

> **APIキー不要で今すぐ試せます。**
> `USE_MOCK_LLM=true`（デフォルト）でモックLLMが起動し、PDF読取 → 法令確認 → ギャップ分析 → 改善提案 → レポート生成が全て動きます。

### CLI（1コマンド）

```bash
# APIキー不要（USE_MOCK_LLM=true がデフォルト）
disclosure-check your_report.pdf --level 竹

# 会社名・年度を指定
disclosure-check your_report.pdf --company-name "株式会社A" --fiscal-year 2025 --level 竹

# 本番LLM（Claude API）を使う場合
export ANTHROPIC_API_KEY=sk-ant-xxx
USE_MOCK_LLM=false disclosure-check your_report.pdf --level 松
```

### Python API（3行）

```python
import os; os.environ.setdefault("USE_MOCK_LLM", "true")
from scripts.m1_pdf_agent import extract_report
report = extract_report("your_report.pdf", company_name="株式会社A", fiscal_year=2025)
print(report.company_name, "—", len(report.sections), "sections extracted")
```

### フルパイプライン（M1→M5）

```python
import os
os.environ["USE_MOCK_LLM"] = "true"  # 本番LLMを使う場合はこの行を削除

from scripts.m1_pdf_agent import extract_report
from scripts.m2_law_agent import load_law_context
from scripts.m3_gap_analysis_agent import analyze_gaps
from scripts.m4_proposal_agent import generate_proposals
from scripts.m5_report_agent import generate_report

report     = extract_report("your_report.pdf", company_name="株式会社A", fiscal_year=2025)
law_ctx    = load_law_context()
gap_result = analyze_gaps(report, law_ctx)
proposals  = [generate_proposals(g) for g in gap_result.gaps if g.has_gap]
markdown   = generate_report(report, law_ctx, gap_result, proposals, level="竹")
print(markdown)
```

### Web UI（Docker）

```bash
cp .env.example .env   # APIキーは任意（モックで動作）
docker compose up --build
```

| サービス | URL | 説明 |
|----------|-----|------|
| Web UI | http://localhost:3010 | PDF アップロード → ブラウザでレポート確認 |
| サンプル | http://localhost:3010/sample | PDFなしで分析結果を即確認 |
| REST API | http://localhost:8010 | JSON API（自動化用） |
| API仕様 | http://localhost:8010/docs | Swagger UI |

---

## テスト実行

```bash
# APIキー不要でテスト全件実行（747テスト）
USE_MOCK_LLM=true python3 -m pytest -x -q

# 特定ファイルのみ
USE_MOCK_LLM=true python3 -m pytest scripts/test_m3_gap_analysis.py -v
```

> `testpaths = ["tests", "scripts"]` が `pyproject.toml` に設定済みのため、パス指定なしで全テストを収集します。

---

## プロジェクト構造

```
disclosure-multiagent/
├── scripts/                 # M1〜M9 エージェント本体 + テスト
│   ├── m1_pdf_agent.py      # PDF解析・セクション抽出
│   ├── m2_law_agent.py      # 法令YAML読込・照合
│   ├── m3_gap_analysis_agent.py  # ギャップ分析（LLM）
│   ├── m4_proposal_agent.py # 松竹梅提案生成
│   ├── m5_report_agent.py   # Markdownレポート出力
│   ├── m6_law_url_collector.py   # 法令URL自動収集
│   ├── m7_edinet_client.py  # EDINET PDF取得
│   ├── m8_multiyear_agent.py # 複数年比較
│   ├── m9_document_exporter.py   # Word/Excel出力
│   └── test_*.py            # テスト（747件）
├── tests/                   # 追加テスト（A2A等）
│   └── test_a2a.py          # A2Aプロトコルテスト
├── laws/                    # 法令マスターYAML
│   ├── human_capital_2024.yaml
│   ├── ssbj_2025.yaml       # SSBJ最終基準25件
│   └── shoshu_notice_2025.yaml
├── profiles/                # Big4開示チェックプロファイル
│   ├── deloitte/
│   ├── kpmg/
│   ├── pwc/
│   └── ey/
├── api/                     # FastAPI REST API
├── web/                     # Next.js フロントエンド
├── docs/                    # ドキュメント
└── pyproject.toml
```

---

## アーキテクチャ（M1〜M9）

```
有価証券報告書 PDF
      │
      ▼
[M1] PDF パーサ          — セクション抽出（有報 / 招集通知）
      │
      ├──────────────────────────────────────┐
      ▼                                      ▼
[M2] 法令コンテキスト読込  — 法令YAML照合   [M8] 複数年比較
                                             — 年度差・トレンド検出
      ▼
[M3] ギャップ分析器        — LLM: 必須 / 推奨 / 参考
      │
      ▼
[M4] 提案生成器            — 松竹梅 3段階の改善文案
      │
      ▼
[M5] レポート組立          — Markdown レポート出力
      │
      ├──────────┐
      ▼          ▼
[M9] Word/Excel  [M7] EDINET クライアント — 有報PDF自動取得
                 [M6] 法令URL収集 — 金融庁/e-Gov URL自動取得
```

| モジュール | 役割 | テスト数 |
|-----------|------|---------|
| `m1_pdf_agent.py` | PDF解析・セクション分割 | 47 |
| `m2_law_agent.py` | 法令YAML読込・参照期間計算 | 26 |
| `m3_gap_analysis_agent.py` | LLMによるギャップ分析 | 23 |
| `m4_proposal_agent.py` | 松竹梅提案生成 | 48 |
| `m5_report_agent.py` | レポート組立 | 46 |
| `m6_law_url_collector.py` | 金融庁/e-Gov URL収集 | 13 |
| `m7_edinet_client.py` | EDINET PDF取得 | 15 |
| `m8_multiyear_agent.py` | 複数年比較分析 | 15 |
| `m9_document_exporter.py` | Word/Excel エクスポート | 12 |

**合計: 747テスト、全件PASS**

---

## 環境変数

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `USE_MOCK_LLM` | `true` | `true` = APIキー不要でテスト・デモ実行可 |
| `ANTHROPIC_API_KEY` | — | 本番LLM使用時に必要（`USE_MOCK_LLM=false` 時） |
| `EDINET_SUBSCRIPTION_KEY` | — | 任意 — EDINET検索API（M7-2）で必要。[申請はこちら](https://disclosure2.edinet-fsa.go.jp/WZEK0010.aspx) |
| `LAW_YAML_DIR` | `laws/` | カスタム法令YAMLディレクトリ |

`.env.example` を `.env` にコピーしてください。

---

## EDINET から有報PDFを取得する方法

EDINETは金融庁が提供する無料の開示書類システムです。

→ **[docs/how_to_get_yuho.md](docs/how_to_get_yuho.md)** に手順を記載しています。

または M7 クライアントで直接取得:

```python
from scripts.m7_edinet_client import EdinetClient
client = EdinetClient()
pdf_path = client.download_latest_yuho("E02142")  # トヨタ自動車
```

---

## 関連OSS

同作者が開発する財務・AI品質系 OSS のエコシステムです。

| OSS | 説明 | 状態 |
|-----|------|------|
| [fixed-asset-agentic](https://github.com/Majiro-ns/fixed-asset-agentic) | 固定資産台帳AI解析（償却計算・異常検知） | 公開中 |
| [agent-quality-gate](https://github.com/Majiro-ns/agent-quality-gate) | AIエージェント品質ゲート（自信度・クロスレビュー検証） | 公開中 |
| [xbrl-ai-analyzer](https://github.com/Majiro-ns/xbrl-ai-analyzer) | XBRL財務データAI解析（EDINETデータ構造化） | 準備中 |
| [nencho](https://github.com/Majiro-ns/nencho) | 年末調整AI支援スキルパッケージ | 公開中 |

---

## コントリビューション

Pull Request 歓迎です。特に以下を歓迎します:

- **法令YAMLの更新** — 規制は毎年改正されます
- **新しい `doc_type` 対応** — 統合報告書・サステナビリティレポート等
- **テストフィクスチャ** — `tests/fixtures/` 配下のサンプルPDF
- **バグ修正・パフォーマンス改善**

PR前に `USE_MOCK_LLM=true python3 -m pytest -q` の全件PASSを確認してください。

詳細は [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。

---

## 免責事項

本ツールはPoC（概念実証）です。税務・法律上の判断には必ず専門家の確認が必要です。
本ツールが生成した分析結果は、提出前に**必ずご自身で内容を確認**してください。
税制・開示規制は毎年改正されます。本ツールが参照する法令データの更新状況を確認の上ご利用ください。

---

## ライセンス

MIT License — Copyright 2026 Majiro-ns

詳細は [LICENSE](LICENSE) を参照してください。

---

## 謝辞・参考

- [EDINET API](https://disclosure2.edinet-fsa.go.jp/) — 金融庁 電子開示システム
- [SSBJ（サステナビリティ基準委員会）最終基準](https://www.ssb-j.org/) — 2025年3月施行
- [内閣官房 人的資本可視化指針](https://www.cas.go.jp/jp/houdou/220830jinzai.html)（2022年8月）
- [金融庁 企業内容等の開示に関する内閣府令](https://www.fsa.go.jp/policy/disclosure/index.html)
