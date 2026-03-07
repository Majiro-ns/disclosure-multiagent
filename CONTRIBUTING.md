# Contributing to disclosure-multiagent

Thank you for your interest in contributing!
This project follows a **松竹梅 (Plum / Bamboo / Pine) grading system** for corporate disclosure improvement suggestions.

---

## Table of Contents

- [Issues](#issues)
- [Pull Requests](#pull-requests)
- [Development Setup](#development-setup)
- [Running Tests (Mock mode)](#running-tests-mock-mode)
- [Adding a Law YAML](#adding-a-law-yaml)
- [Code Style](#code-style)

---

## Issues

Please use GitHub Issues for:

- **Bug reports** — Include Python version, OS, error traceback, and minimal reproduction steps.
- **Law YAML requests** — If a disclosure law / regulation is not yet covered, open an Issue with:
  - Law name and article number
  - Effective date
  - Source URL (e.g., e-Gov, 金融庁, SSBJ website)
- **Feature requests** — Describe the use case and expected behavior.

> **Note on law accuracy**: The YAML rules in `laws/` reflect the regulations as of their `effective_period`.
> If you find an inaccuracy, please open an Issue with the authoritative source.

---

## Pull Requests

### Before opening a PR

1. Check that an Issue exists (or open one first for non-trivial changes).
2. Fork the repository and create a branch from `main`:
   ```
   git checkout -b feat/your-feature-name
   ```
3. Make sure tests pass in Mock mode (see [Running Tests](#running-tests-mock-mode)).
4. Keep each PR focused — one feature or fix per PR.

### PR checklist

- [ ] Tests pass (`python -m pytest scripts/ -x` with `USE_MOCK_LLM=true`)
- [ ] New code is covered by tests
- [ ] Law YAML additions follow the [schema](#adding-a-law-yaml)
- [ ] Commit messages are in English or Japanese (`feat:`, `fix:`, `docs:`, `test:` prefix preferred)

---

## Development Setup

### Requirements

- Python 3.10 or later
- (Optional) Japanese fonts for PDF generation:
  - Linux: `sudo apt install fonts-noto-cjk`
  - Windows (WSL): `NotoSansJP-VF.ttf` in `C:\Windows\Fonts\`

### Install

```bash
git clone https://github.com/Majiro-ns/disclosure-multiagent.git
cd disclosure-multiagent

# Core + dev dependencies
pip install -e ".[dev]"

# Full install (includes LLM, API server, UI)
pip install -e ".[all]"
```

### Environment variables

Copy the example file:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `USE_MOCK_LLM` | `true` | Skip Anthropic API calls (use stub responses) |
| `USE_MOCK_EDINET` | `true` | Skip EDINET API calls (use local fixtures) |
| `ANTHROPIC_API_KEY` | — | Required only when `USE_MOCK_LLM=false` |
| `EDINET_SUBSCRIPTION_KEY` | — | Required only when `USE_MOCK_EDINET=false` |

**For local development, keep both mock flags `true`. No API keys needed.**

---

## Running Tests (Mock mode)

All tests can run without API keys:

```bash
# Run all tests in Mock mode
USE_MOCK_LLM=true USE_MOCK_EDINET=true python -m pytest scripts/ -x --tb=short

# Run a specific test file
USE_MOCK_LLM=true python -m pytest scripts/test_m1_pdf_agent.py -v

# Run tests for the sample PDF generator
python -m pytest scripts/test_generate_sample_pdf.py -v

# Run with coverage
USE_MOCK_LLM=true USE_MOCK_EDINET=true python -m pytest scripts/ --cov=scripts --cov-report=term-missing
```

### Test fixture (sample PDF)

The repository includes a pre-generated fixture PDF at `tests/fixtures/sample_yuho.pdf`.
This is a fictional company ("株式会社テスト商事") annual report at the **梅 (60-point) disclosure level**.

To regenerate it:

```bash
python scripts/generate_sample_pdf.py
```

---

## Adding a Law YAML

Law check items live in `laws/`. The system auto-loads all `laws/*.yaml` at startup.

### Naming convention

```
{category}-{year}.yaml

Examples:
  laws/human_capital_2024.yaml   → hc-2024-xxx
  laws/ssbj_2025.yaml            → sb-2025-xxx
  laws/climate_2026.yaml         → cl-2026-xxx
```

| Prefix | Category |
|---|---|
| `hc-` | 人的資本 (Human Capital) |
| `sb-` | SSBJ (Sustainability Disclosure) |
| `gm-` | 総会前開示 (General Meeting) |
| `gc-` | ガバナンス (Governance) |
| `bk-` | 銀行業 (Banking / Basel III) |
| `cl-` | 気候変動 (Climate) |

### YAML schema

```yaml
version: "1.0"
effective_period:
  from: "2025-04-01"
  to: "2026-03-31"

amendments:
  - id: "hc-2025-001"
    title: "女性管理職比率の開示"
    category: "人的資本"
    required_items:
      - "女性管理職比率（%）を数値で記載すること"
      - "目標値と達成期限を併記すること"
    reference:
      law: "女性活躍推進法 第20条"
      article: "有価証券報告書の記載基準（2023年改正）"
```

### Steps to add a new YAML

1. Create the file in `laws/` following the naming convention.
2. Validate the schema:
   ```bash
   python -c "
   import yaml, sys
   data = yaml.safe_load(open('laws/your_new_file.yaml'))
   entries = data.get('amendments') or data.get('entries', [])
   print(f'Loaded {len(entries)} entries')
   "
   ```
3. Run the law agent tests to confirm auto-loading:
   ```bash
   USE_MOCK_LLM=true python -m pytest scripts/test_m2_law_agent.py -v
   ```
4. Update `laws/README.md` with the new file entry.
5. Open a PR with the YAML and a link to the authoritative source.

> **Accuracy matters**: Law YAMLs directly affect disclosure advice.
> Always cite the official source (`reference.law` + `reference.article`).
> Outdated or incorrect rules are worse than missing ones.

---

## Code Style

- Python: follow PEP 8. No strict formatter enforced yet (black / ruff PRs welcome).
- Tests: use `pytest`. Place test files in `scripts/test_*.py` or `tests/test_*.py`.
- Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:` prefixes preferred.
- No hardcoded absolute paths (e.g., `/mnt/c/Users/...`). Use `Path(__file__).parent` or env vars.

---

## Questions?

Open an Issue or start a Discussion on GitHub.
The law YAML format and the 松竹梅 scoring system are explained in `docs/`.
