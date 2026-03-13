# disclosure-multiagent

[![CI](https://github.com/Majiro-ns/disclosure-multiagent/actions/workflows/test.yml/badge.svg)](https://github.com/Majiro-ns/disclosure-multiagent/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-408%2B%20passing-brightgreen)](tests/)
[![Mock Mode](https://img.shields.io/badge/mock%20mode-no%20API%20key%20needed-orange)](docs/)

**Drop your annual securities report PDF. Get a 3-tier improvement plan — no consulting required.**

> 「100点の開示事例は金融庁が教えてくれる。60点で確実に法令を超える方法は、誰も教えてくれない。」
> *The FSA shows you 100-point disclosure. Nobody teaches you how to reliably clear 60 points.*

---

## 30秒で何ができるか

```
あなたの有報PDF を入力
        ↓
① PDF読取   — 有報のセクションを自動抽出
        ↓
② 法令確認  — 最新の開示規制YAMLと照合
        ↓
③ ギャップ分析 — 「何が足りないか」を検出
        ↓
④ 改善提案  — 梅・竹・松 3段階の記載文案を生成
        ↓
⑤ レポート生成 — Markdown レポートとして出力
```

→ **Web UI起動後** ブラウザで `/sample` を開くと架空企業データの分析結果（ギャップ5件・松竹梅提案・全文レポート）を即確認できます
→ **CLIで試したい場合** は `tests/fixtures/sample_yuho.pdf`（架空有報）をそのまま使えます（[サンプルデータ詳細](web/public/sample_report.json)）

---

## What is this?

`disclosure-multiagent` is an open-source AI pipeline that analyzes Japanese corporate disclosure documents (有価証券報告書 / 株主総会招集通知) and generates a **松竹梅 (3-tier) improvement plan** showing exactly what to add, fix, or enhance.

| Tier | Score | Description |
|------|-------|-------------|
| 梅 *Ume* | 60 pts | **Compliance baseline** — do this and you won't be flagged |
| 竹 *Take* | 80 pts | **Industry standard** — on par with your peers |
| 松 *Matsu* | 100 pts | **Best-in-class** — recognized by institutional investors |

**No API key needed to try it** — mock mode is built in.

---

## Three Ways to Use It

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1 │  OSS Library     pip install disclosure-multiagent       │
│          │  Use M1-M9 agents directly in your Python code           │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 2 │  CLI Tool        disclosure-check your_yuho.pdf          │
│          │  One command → Markdown report (no server needed)        │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 3 │  Web UI          docker compose up                       │
│          │  Full stack: browser UI + REST API + PDF upload          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

> **APIキー不要で今すぐ試せます。** `USE_MOCK_LLM=true`（デフォルト）でモックLLMが起動し、
> PDF読取 → 法令確認 → ギャップ分析 → 改善提案 → レポート生成 が全て動きます。
> 本番LLMに切り替えるには `ANTHROPIC_API_KEY` を設定するだけです。

---

### Layer 1 — OSS Library (Python, 3 lines)

```bash
pip install disclosure-multiagent
```

```python
# Minimum working example — copy and paste as-is
import os; os.environ.setdefault("USE_MOCK_LLM", "true")
from scripts.m1_pdf_agent import extract_report
report = extract_report("your_report.pdf")
print(report.company_name, "—", len(report.sections), "sections extracted")
```

> `USE_MOCK_LLM` defaults to `true` — no API key needed.
> Pass `company_name` and `fiscal_year` for a richer report:

```python
import os; os.environ.setdefault("USE_MOCK_LLM", "true")
from scripts.m1_pdf_agent import extract_report
report = extract_report("your_report.pdf", company_name="株式会社A", fiscal_year=2025)
print(report.company_name, "—", len(report.sections), "sections")
# → For the full 松竹梅 gap analysis pipeline, see example below
```

Full pipeline (M1→M5 individually):

```python
import os
os.environ["USE_MOCK_LLM"] = "true"  # remove this line when using real Claude API

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

---

### Layer 2 — CLI Tool (one command)

```bash
pip install disclosure-multiagent
```

```bash
# Mock mode — no API key needed (USE_MOCK_LLM=true is the default)
disclosure-check your_report.pdf --level 竹

# With company name and fiscal year
disclosure-check your_report.pdf --company-name "株式会社A" --fiscal-year 2025 --level 竹

# → Markdown report saved to scripts/reports/report_株式会社A_2025_<timestamp>.md
```

```bash
# Real LLM mode — requires Claude API key
export ANTHROPIC_API_KEY=sk-ant-xxx
USE_MOCK_LLM=false disclosure-check your_report.pdf --level 松
```

---

### Layer 3 — Web UI (Docker, full stack)

```bash
git clone https://github.com/Majiro-ns/disclosure-multiagent.git
cd disclosure-multiagent

# Configure (API key optional — mock works without it)
cp .env.example .env

# Start (docker-compose v1) or (docker compose v2)
docker-compose up --build
# docker compose up --build   ← use this if docker-compose v1 is not installed
```

Open in browser (ready in ~30–60 seconds after first build):

| Service | URL | Description |
|---------|-----|-------------|
| **Web UI** | http://localhost:3010 | PDF upload → report in browser |
| **Sample** | http://localhost:3010/sample | Interactive sample report — no PDF needed |
| REST API | http://localhost:8010 | JSON API for automation |
| API Docs | http://localhost:8010/docs | Swagger UI |

```bash
docker-compose down   # Stop all services
```

---

## 🚀 UIクイックスタート（Docker不要・npm版）

### 方法A（UI閲覧のみ・APIキー不要）

```bash
cd disclosure-multiagent/web
npm install && npm run dev
```

→ http://localhost:3000 で確認（`/sample` ページはAPIなしで閲覧可）

### 方法B（フルスタック・AI分析も動作）

```powershell
# ターミナル1（バックエンド）
$env:USE_MOCK_LLM='true'; python -m uvicorn api.main:app --port 8010
```

```bash
# ターミナル2（フロントエンド）
cd web && npm run dev
```

→ http://localhost:3000 で PDF アップロード + AI 分析が全て動作

---

## Sample Output

Running `disclosure-check` produces a Markdown report. Here is a representative excerpt:

```markdown
# 開示ギャップ分析レポート — 株式会社サンプル商事（2024年度）

**提案レベル**: 竹（業界標準水準）　**ギャップ数**: 3件検出

## ギャップ概要

| # | 項目 | 判定 | 優先度 |
|---|------|------|--------|
| 1 | 従業員エンゲージメント指標 | 修正必須（義務規定） | 高 |
| 2 | 人材育成投資額（数値開示） | 強化推奨 | 中 |
| 3 | 温室効果ガス排出量 Scope1/2 | 強化推奨 | 中 |

## 改善提案（竹水準 — 業界標準）

### GAP-001: 従業員エンゲージメント指標の開示

**現状**: 記載なし（義務規定・対応必須）

**改善案（竹）**:
当社は、従業員エンゲージメントを経営の重要指標と位置づけ、年1回の全社サーベイを実施しております。
直近のエンゲージメントスコアは[数値]点であり、前年度比[増減]点の[改善／低下]となりました。

*根拠: 内閣官房「人的資本可視化指針」§4（2022年8月）*
```

→ **[Full sample report (JSON)](web/public/sample_report.json)**
→ **Interactive version**: `docker compose up` 後 http://localhost:3010/sample でギャップ一覧・提案・全文レポートをブラウザで確認できます

---

## Architecture

```
Annual Report PDF
      │
      ▼
[M1] PDF Parser          — Section extraction (有報 / 招集通知)
      │
      ├──────────────────────────────────────┐
      ▼                                      ▼
[M2] Law Context Loader  — YAML law master  [M8] Multi-Year Comparator
      │                                          — YearDiff / trend detection
      ▼
[M3] Gap Analyzer        — LLM: required / recommended / reference
      │
      ▼
[M4] Proposal Generator  — 松竹梅 (3-tier) improvement text
      │
      ▼
[M5] Report Assembler    — Markdown report with disclaimer
      │
      ├──────────┐
      ▼          ▼
[M9] Word/Excel  [M7] EDINET Client  — auto-download annual report PDFs
                 [M6] Law URL Collector — auto-fetch FSA / e-Gov URLs
```

| Module | Role | Tests |
|--------|------|-------|
| `m1_pdf_agent.py` | PDF parsing, section splitting | 47 |
| `m2_law_agent.py` | Law YAML loading, reference period calc | 26 |
| `m3_gap_analysis_agent.py` | Gap analysis via LLM | 23 |
| `m4_proposal_agent.py` | 松竹梅 proposal generation | 48 |
| `m5_report_agent.py` | Report assembly | 46 |
| `m6_law_url_collector.py` | FSA / e-Gov URL collection | 13 |
| `m7_edinet_client.py` | EDINET PDF download | 15 |
| `m8_multiyear_agent.py` | Multi-year comparison | 15 |
| `m9_document_exporter.py` | Word / Excel export | 12 |

**Total: 408+ tests, all passing**

---

## Installation

### Minimal (core pipeline only)

```bash
pip install pymupdf pyyaml
```

### With real LLM support

```bash
pip install "disclosure-multiagent[llm]"
# or: pip install pymupdf pyyaml anthropic
```

### Full install (API server + dev tools)

```bash
pip install "disclosure-multiagent[llm,api,dev]"
```

### From source

```bash
git clone https://github.com/Majiro-ns/disclosure-multiagent.git
cd disclosure-multiagent
pip install -e ".[dev]"
```

---

## Document Types

| `doc_type` | Document | Notes |
|------------|----------|-------|
| `"yuho"` | 有価証券報告書 (Annual Securities Report) | Default |
| `"shoshu"` | 株主総会招集通知 (Notice of General Meeting) | AGM-specific sections |

```python
from scripts.m1_pdf_agent import extract_report

# Annual report (default)
report = extract_report("yuho.pdf", company_name="株式会社A", fiscal_year=2025)

# Notice of general meeting
report = extract_report("shoshu.pdf", company_name="株式会社A", fiscal_year=2025, doc_type="shoshu")
```

---

## Law YAML (`laws/`)

The `laws/` directory contains law master YAML files. All files are auto-loaded at startup.

| File | Items | Coverage |
|------|-------|---------|
| `human_capital_2024.yaml` | 8 | Human capital disclosure (FSA 2024) + SSBJ 2024 |
| `ssbj_2025.yaml` | 25 | SSBJ 2025 standards (sb-2025-001 to sb-2025-025) |
| `shareholder_notice_2025.yaml` | 16 | AGM disclosure + governance |
| `banking_2025.yaml` | — | Banking-sector specifics |

**Data as of 2024. PRs to update are welcome.**

To add a new regulation, drop a YAML file into `laws/` — no restart needed.
Schema: [`docs/law_yaml_schema.md`](docs/law_yaml_schema.md)

---

## Getting Annual Report PDFs

You can download annual report PDFs from EDINET (Financial Services Agency's disclosure system) for free.

See **[docs/how_to_get_yuho.md](docs/how_to_get_yuho.md)** for step-by-step instructions.

Or use the built-in M7 client:

```python
from scripts.m7_edinet_client import EdinetClient
client = EdinetClient()
pdf_path = client.download_latest_yuho("E02142")  # Toyota Motor
```

---

## Streamlit UI

```bash
cd scripts/
streamlit run app.py
# → http://localhost:8501
```

Upload a PDF → M1–M5 full pipeline runs in browser.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_MOCK_LLM` | `true` | `true` = no API key needed |
| `ANTHROPIC_API_KEY` | — | Required when `USE_MOCK_LLM=false` |
| `EDINET_SUBSCRIPTION_KEY` | — | Optional — for EDINET search API (M7-2). [Apply here →](https://disclosure2.edinet-fsa.go.jp/WZEK0010.aspx) |
| `LAW_YAML_DIR` | `laws/` | Custom law YAML directory |

Copy `.env.example` to `.env` to get started.

---

## A2A (Agent-to-Agent) Protocol Support

disclosure-multiagent は [A2A プロトコル](https://google.github.io/A2A/) に対応しており、
外部エージェントから直接呼び出すことができます。

### Agent Card 取得

```bash
curl http://localhost:8000/.well-known/agent-card.json
```

### 外部エージェントからの接続

```python
import httpx
import uuid

# A2A タスクを送信
task = {
    "id": str(uuid.uuid4()),
    "contextId": str(uuid.uuid4()),
    "message": {
        "messageId": str(uuid.uuid4()),
        "role": "user",
        "parts": [{"kind": "text", "text": "EDINETコード E12345 の有価証券報告書を松竹梅分析してください"}]
    }
}
resp = httpx.post("http://localhost:8000/a2a/execute", json=task)
result = resp.json()
print(result["artifacts"][0]["parts"][0]["text"])
```

### 利用可能なスキル

| スキルID | 説明 | 入力例 |
|----------|------|--------|
| `analyze_disclosure` | 有価証券報告書の松竹梅分析 | 「EDINETコード E12345 を分析してください」 |
| `edinet_search` | EDINET書類検索 | 「証券コード 7203 の有価証券報告書を検索」 |
| `matsu_take_ume_scoring` | テキストの松竹梅スコアリング | 「スコアリング対象: 離職率3.5%（目標2025年度）」 |

スキルは `skillId` で明示指定するか、入力テキストのキーワードで自動振り分けされます。

---

## 関連OSS

同作者が開発する財務・AI品質系OSSのエコシステムです。

| OSS | 説明 | 状態 |
|-----|------|------|
| [fixed-asset-agentic](https://github.com/Majiro-ns/fixed-asset-agentic) | 固定資産台帳AI解析（償却計算・異常検知） | 公開中 |
| [agent-quality-gate](https://github.com/Majiro-ns/agent-quality-gate) | AIエージェント品質ゲート（自信度・クロスレビュー検証） | 公開中 |
| [xbrl-ai-analyzer](https://github.com/Majiro-ns/xbrl-ai-analyzer) | XBRL財務データAI解析（EDINETデータ構造化） | 準備中 |

---

## Contributing

Pull requests are welcome, especially for:

- **Law YAML updates** — regulations change every year
- **New doc_type support** — integrated reports, sustainability reports
- **Test fixtures** — sample PDFs under `tests/fixtures/`
- **Bug fixes and performance improvements**

Please run `pytest` before submitting a PR.

---

## License

MIT License — Copyright 2026 Majiro-ns

See [LICENSE](LICENSE) for full text.

---

## 日本語セクション

### このツールでできること

自社の有価証券報告書（有報）PDFを入れるだけで、人的資本開示・SSBJなどの法令要件に対して **何が足りないか・どう改善すればいいか** を松竹梅3段階で自動生成します。

- **梅（60点）**: 法令準拠ライン。これだけやれば監督官庁から指摘されない
- **竹（80点）**: 業界標準。同業他社と遜色ない水準
- **松（100点）**: 先進開示。機関投資家から評価される水準

### なぜこれを作ったか

> 「**松の事例は国も教えてくれるが、竹や梅は決して教えてくれない。**」

100点（松）の開示事例は金融庁も教えてくれる。60点（梅）で確実に法令を超える方法・80点（竹）の業界標準水準は、誰も教えてくれない。コンサルを呼ばなくても、自社の開示担当者が自力で改善点を把握できるツールを目指しています。

### EDINET から有報PDFを取得する方法

→ [docs/how_to_get_yuho.md](docs/how_to_get_yuho.md) を参照してください。

### 免責事項

本ツールはPoC（概念実証）です。税務・法律上の判断には必ず専門家の確認が必要です。
