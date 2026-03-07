# disclosure-multiagent

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-318%2B%20passing-brightgreen)](tests/)
[![Mock Mode](https://img.shields.io/badge/mock%20mode-no%20API%20key%20needed-orange)](docs/)

**Drop your annual securities report PDF. Get a 3-tier improvement plan — no consulting required.**

> 「100点の開示事例は金融庁が教えてくれる。60点で確実に法令を超える方法は、誰も教えてくれない。」
> *The FSA shows you 100-point disclosure. Nobody teaches you how to reliably clear 60 points.*

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

> **Mock mode** (`USE_MOCK_LLM=true`): runs the full M1→M5 pipeline with a built-in fake LLM.
> PDF parsing, law loading, gap detection, and report generation all work — **no API key, no cost**.
> Switch to real LLM any time by setting `ANTHROPIC_API_KEY`.

---

### Layer 1 — OSS Library (Python, 3 lines)

```bash
pip install disclosure-multiagent
```

```python
# Minimum working example — copy and paste as-is
from scripts.run_pipeline import main
result = main("your_report.pdf")
print(result)
```

> `USE_MOCK_LLM` defaults to `true` — no API key needed.
> Pass `company_name` and `fiscal_year` for a richer report:

```python
from scripts.run_pipeline import main
result = main("your_report.pdf", company_name="株式会社A", fiscal_year=2025, level="竹")
print(result)
# → Markdown report with 松竹梅 gap analysis printed to stdout
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

Open in browser:

| Service | URL | Description |
|---------|-----|-------------|
| **Web UI** | http://localhost:3010 | PDF upload → report in browser |
| REST API | http://localhost:8010 | JSON API for automation |
| API Docs | http://localhost:8010/docs | Swagger UI |

```bash
docker-compose down   # Stop all services
```

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

**Total: 318+ tests, all passing**

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
| `EDINET_SUBSCRIPTION_KEY` | — | Optional — for EDINET search API (M7-2) |
| `LAW_YAML_DIR` | `laws/` | Custom law YAML directory |

Copy `.env.example` to `.env` to get started.

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

「100点の開示事例は金融庁が教えてくれる。60点で確実に法令を超える方法は、誰も教えてくれない。」

コンサルを呼ばなくても、自社の開示担当者が自力で改善点を把握できるツールを目指しています。

### EDINET から有報PDFを取得する方法

→ [docs/how_to_get_yuho.md](docs/how_to_get_yuho.md) を参照してください。

### 免責事項

本ツールはPoC（概念実証）です。税務・法律上の判断には必ず専門家の確認が必要です。
