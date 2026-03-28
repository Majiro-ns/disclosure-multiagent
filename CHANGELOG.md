# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - PhaseC Extensions

### Added

#### PhaseC: 拡張プロファイル機能（開示品質強化）

- **拡張プロファイル追加** (`profiles/deloitte/`, `profiles/kpmg/`, `profiles/pwc/`, `profiles/ey/`): 大手監査法人の開示観点に対応した拡張YAMLプロファイル。各プロファイル17件以上（デフォルト非同梱）。
  - `PhaseC-02`: 拡張プロファイル強化（各+3エントリ）— `TestBigFourProfilesPhaseCEY`, `TestBigFourProfilesPhaseCPwC`
  - `PhaseC-05`: 業界別プロファイル3種（金融・製造・IT）— `TestIndustryProfiles`
  - `PhaseC-06`: 拡張プロファイル各+3エントリ（各17件到達）— `TestBigFourProfilesPhaseC` (BPC-01〜03)
  - `PhaseC-07`: リスク管理・内部統制拡張プロファイル（`profiles/ey/ey_risk_control_profile.yaml`）20件 — IC/DX/SC/NR/AQ 5カテゴリ — `TestBigFourProfilesPhaseCEYRiskControl`
- **テスト拡充**: 637 → 735 件 (+98)

#### OSS公開品質整備

- `README.md` 日本語全面改訂: 9セクション完備（概要/特徴/インストール/クイックスタート/テスト実行/プロジェクト構造/アーキテクチャ/環境変数/ライセンス）
- バッジ更新: `tests-735 passing`

#### Infrastructure

- FSA RSS対応 法令更新パイプライン拡張 (`m6_law_url_collector.py`)
- A2A通信テスト (`tests/test_a2a.py`)

---

## [1.0.0] - 2026-03-07

### Added

#### M1–M9 Pipeline (End-to-End)

- **M1 — PDF Parser** (`scripts/m1_pdf_agent.py`): PyMuPDF-based parser.
  Extracts structured sections from annual-report PDFs with graceful degradation
  (returns empty `StructuredReport` on parse error instead of raising).
  Avg. 0.828 s/document (10-company benchmark). Supports `yuho` and `shoshu` doc types.
- **M2 — Law Context Agent** (`scripts/m2_law_agent.py`): Loads YAML law-DB
  (`laws/`) and returns applicable `LawEntry` list filtered by fiscal year,
  month-end, and target market. Supports `amendments` top-level key schema.
- **M3 — Gap Analysis Agent** (`scripts/m3_gap_analysis_agent.py`): Two-stage
  detection — keyword filter (`SSBJ_KEYWORDS` 25 terms + `HUMAN_CAPITAL_KEYWORDS`
  + `BANKING_KEYWORDS`) then Claude Haiku LLM context judgement.
  All gap findings carry a law-reference ID (`HC_20260220_001` etc.) for audit
  traceability.
- **M4 — 松竹梅 Proposal Agent** (`scripts/m4_proposal_agent.py`): Generates
  three-tier improvement proposals (松=comprehensive / 竹=standard / 梅=minimal)
  via few-shot prompting. Placeholder markers (`[平均年間給与額]` etc.) flag items
  requiring manual completion.
- **M5 — Report Agent** (`scripts/m5_report_agent.py`): Produces Markdown
  disclosure-gap reports (disclaimer → meta → gap summary table → section
  proposals → law reference list). Includes Streamlit UI
  (`_is_streamlit_running()` detection for dual CLI/web support).
- **M6 — Law URL Collector** (`scripts/m6_law_url_collector.py`): Queries
  e-Gov API to auto-populate `source` URLs in law YAMLs.
- **M7 — EDINET Client** (`scripts/m7_edinet_client.py`): Downloads annual-
  report PDFs from EDINET API. Supports `DocTypeCode.yuho` / `.shoshu`.
  `batch_fetch_companies()` processes multiple companies; `BatchCompanyResult`
  dataclass tracks per-company outcome (`success`, `elapsed_sec`, `error`).
  DOS guard: `REQUEST_DELAY = 3.0 s` between real-API calls; skipped in mock mode.
- **M8 — Multi-Year Analyzer** (`scripts/m8_multiyear.py`): Compares gap
  analysis results across fiscal years to surface year-over-year regression.
- **M9 — Document Exporter** (`scripts/m9_document_exporter.py`): Exports
  gap reports to Word (`.docx`) and Excel (`.xlsx`) for enterprise handoff.

#### 松竹梅 3-Tier Improvement Proposals

Structured few-shot examples for every detected gap:
- **松 (comprehensive)**: detailed disclosures with KPIs, international standards
  (ISSB/GRI), and third-party verification references.
- **竹 (standard)**: meeting minimum requirements with placeholder prompts.
- **梅 (minimal)**: concise text satisfying only mandatory items.

#### Mock Mode (API-key-free testing)

- `USE_MOCK_LLM=true` — M3/M4 return deterministic mock responses; no
  `ANTHROPIC_API_KEY` required.
- `USE_MOCK_EDINET=true` — M7 serves fixture PDFs from `10_Research/samples/`;
  no `EDINET_SUBSCRIPTION_KEY` required.
- All 375 tests pass under mock mode (`USE_MOCK_LLM=true USE_MOCK_EDINET=true`).

#### EDINET API Integration (M7 batch analysis)

- `batch_fetch_companies(companies, download_dir, request_delay)` — processes a
  list of `{company_name, year}` dicts and returns ordered `BatchCompanyResult` list.
- CLI `--batch` option accepts JSON: `{"companies":[{"company_name":"…","year":2023}]}`.
- DOS countermeasure: `REQUEST_DELAY = 3.0 s` constant; mock mode skips sleep.

#### SSBJ (Sustainability Standards Board of Japan) Support

- `laws/ssbj_2025.yaml` — 25 SSBJ Final Standard check items (effective
  2025-03-31), covering the four-pillar structure:
  - Governance (sb-2025-001–003, 3 items)
  - Strategy (sb-2025-004–010, 7 items)
  - Risk Management (sb-2025-011–013, 3 items)
  - Metrics & Targets (sb-2025-014–022, 9 items)
  - General Requirements (sb-2025-023–025, 3 items)
- Checklist items CL-026–035 (`api/data/checklist_data.json`): 10 SSBJ
  disclosure items (`required: true` for Scope1/2, governance, risk, transition
  plan, GHG targets).
- `SSBJ_KEYWORDS` (25 terms) added to M3 for SSBJ section detection.
- M4 few-shot examples for GHG disclosure, GHG reduction targets, and climate
  governance (松竹梅 × 3 sections = 9 examples).

#### 招集通知 (Shoshu / Shareholder Meeting Notice) Support

- `laws/shoshu_notice_2025.yaml` — 16 meeting-notice check items
  (general meeting ×12, corporate governance ×4).
- M1: section detection patterns for notice documents added.
- `DocTypeCode.shoshu` enum added to `schemas.py`; `doc_type_code` field in
  `StructuredReport`.

#### Banking Sector Module

- `BANKING_KEYWORDS` (18 terms): Basel III, CET1/Tier1/Tier2, RWA, LCR, NSFR,
  NPL (non-performing loans), credit risk, IRRBB, etc.
- Merged into `ALL_RELEVANCE_KEYWORDS = HUMAN_CAPITAL_KEYWORDS + SSBJ_KEYWORDS
  + BANKING_KEYWORDS` for bank/trust/securities section detection.
- `m3_gap_analysis_agent.py` banking-sector gap detection confirmed via P9
  cross-review (✅ approved).

#### FastAPI REST API Backend

- Authentication and API-key management (`api/auth.py`).
- `/api/analyze` endpoint: full M1–M5 pipeline via REST (JSON request/response).
- `/api/checklist` endpoint: returns `CL-001–035` check items.
- Scoring API (`scripts/scoring.py`, T012).

#### CLI Entrypoint

- `disclosure-check` command (pyproject `[project.scripts]`):
  ```
  disclosure-check your_yuho.pdf --company-name "株式会社A" \
      --fiscal-year 2025 --level 竹
  ```

#### Law YAML Database

- `laws/human_capital_2024.yaml` — 4 human-capital disclosure items
  (hc-2024-001–004).
- `laws/human_capital_2026.yaml` — 2026-02 Cabinet Office ordinance amendments
  (mandatory salary disclosure, year-on-year wage increase rate).
- `laws/ssbj_2025.yaml` — 25 SSBJ items (see above).
- `laws/shoshu_notice_2025.yaml` — 16 meeting-notice items (see above).

#### OSS Release Preparation

- `.gitignore`, `LICENSE` (MIT), `pyproject.toml` v1.0.0.
- `README.md` full rewrite (three-tier architecture, quickstart, EDINET setup).
- Synthetic sample PDFs (fictional company data) for CI/demo use.
- `[project.urls]`: Homepage / Repository / Issues → `Majiro-ns/disclosure-multiagent`.

### Fixed

- **TC-11 environment dependency** (commit `b0de5d3`): `test_tc11_download_pdf_mock_returns_existing_file`
  was failing in CI and clean-clone environments because it referenced
  `10_Research/samples/company_a.pdf` which did not exist. Fixed by using
  `tmp_path` fixture to create a temporary PDF and `monkeypatch.setattr(m7,
  "_SAMPLES_DIR", tmp_path)` to redirect the lookup — test is now fully
  self-contained.
- **`LAW_YAML_DIR` path** (commit `71cc682`): `m2_law_agent.py` was using an
  incorrect base path for law YAMLs. Corrected to `laws/` relative to the
  project root; `amendments` top-level key schema adopted to match all law YAML
  files.
- **`"物理リスク"` / `"物理的リスク"` inconsistency** (commit `748a049`):
  `SSBJ_KEYWORDS` in `m3_gap_analysis_agent.py` used `"物理的リスク"` while
  the SSBJ Final Standard uses `"物理リスク"`. Unified to `"物理リスク"` across
  implementation and documentation.

---

[1.0.0]: https://github.com/Majiro-ns/disclosure-multiagent/releases/tag/v1.0.0
