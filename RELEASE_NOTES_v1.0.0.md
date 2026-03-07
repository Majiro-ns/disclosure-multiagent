# disclosure-multiagent v1.0.0

**Release date**: 2026-03-14
**License**: MIT

> 「松の事例は国も教えてくれるが、竹や梅は決して教えてくれない。」

---

## What's New

**disclosure-multiagent v1.0.0** is the first public release of an open-source AI pipeline that analyzes Japanese corporate disclosure documents (有価証券報告書 / 株主総会招集通知) and generates a **松竹梅 (3-tier) improvement plan**.

No consulting firm. No API key needed to try it. Just drop your PDF.

---

## Key Features

### M1–M9 End-to-End Pipeline

| Module | Role |
|--------|------|
| M1 PDF Parser | Section extraction from annual-report PDFs (avg. 0.83 s/doc) |
| M2 Law Context Agent | YAML law-DB loading, filtered by fiscal year and market |
| M3 Gap Analyzer | Two-stage detection: keyword filter → LLM context judgement |
| M4 Proposal Generator | 松竹梅 3-tier improvement text via few-shot prompting |
| M5 Report Assembler | Markdown report with audit-traceable law references |
| M6 Law URL Collector | Auto-fetches FSA / e-Gov source URLs |
| M7 EDINET Client | Auto-downloads annual-report PDFs from EDINET API |
| M8 Multi-Year Analyzer | Year-over-year gap regression detection |
| M9 Document Exporter | Word (.docx) / Excel (.xlsx) export for enterprise handoff |

### 松竹梅 (3-Tier) Improvement Proposals

- **梅 (60 pts)** — Compliance baseline: do this and you won't be flagged by regulators
- **竹 (80 pts)** — Industry standard: on par with your peers
- **松 (100 pts)** — Best-in-class: recognized by institutional investors

### Law Coverage

- `human_capital_2024.yaml` — Human capital disclosure (FSA 2024)
- `human_capital_2026.yaml` — 2026-02 Cabinet Office ordinance amendments
- `ssbj_2025.yaml` — 25 SSBJ Final Standard items (4-pillar structure)
- `shoshu_notice_2025.yaml` — 16 AGM disclosure items (招集通知)
- `banking_2025.yaml` — Banking sector: Basel III / CET1 / IRRBB

**Total: 408+ tests passing**

### Mock Mode (API-key-free)

```bash
USE_MOCK_LLM=true disclosure-check your_report.pdf --level 竹
```

The full M1→M5 pipeline runs without any API key. Switch to real Claude LLM any time:

```bash
export ANTHROPIC_API_KEY=sk-ant-xxx
USE_MOCK_LLM=false disclosure-check your_report.pdf --level 松
```

---

## Installation

### From PyPI

```bash
pip install disclosure-multiagent
```

### From source

```bash
git clone https://github.com/Majiro-ns/disclosure-multiagent.git
cd disclosure-multiagent
pip install -e ".[dev]"
```

### Docker (full stack with Web UI)

```bash
cp .env.example .env
docker compose up --build
# → http://localhost:3010
```

---

## Quick Start (3 lines)

```python
import os; os.environ.setdefault("USE_MOCK_LLM", "true")
from scripts.m1_pdf_agent import extract_report
report = extract_report("your_report.pdf", company_name="株式会社A", fiscal_year=2025)
print(report.company_name, "—", len(report.sections), "sections extracted")
```

Or use the CLI:

```bash
disclosure-check your_report.pdf --company-name "株式会社A" --fiscal-year 2025 --level 竹
```

---

## Bug Fixes

- **TC-11 environment dependency**: `test_tc11_download_pdf_mock_returns_existing_file` fixed to use `tmp_path` fixture — fully self-contained in CI
- **`LAW_YAML_DIR` path**: corrected base path for law YAMLs (`laws/` relative to project root)
- **`"物理リスク"` consistency**: unified keyword across `SSBJ_KEYWORDS` and documentation

---

## Acknowledgements

Thank you to everyone who reviewed the SSBJ / human capital disclosure regulations and provided feedback on the 松竹梅 grading framework.

Law YAML contributions and corrections are always welcome — regulations change every year.
See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add a new law YAML.

---

## Links

- **Homepage**: https://github.com/Majiro-ns/disclosure-multiagent
- **Documentation**: https://github.com/Majiro-ns/disclosure-multiagent#readme
- **Issues**: https://github.com/Majiro-ns/disclosure-multiagent/issues
- **EDINET (PDF source)**: https://disclosure2.edinet-fsa.go.jp/
- **SSBJ**: https://www.ssb-j.jp/

---

*This tool is a proof-of-concept (PoC). Always consult qualified professionals for tax and legal judgements.*
