# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.0.x   | ✅ Yes    |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Use [GitHub Security Advisories](https://github.com/Majiro-ns/disclosure-multiagent/security/advisories/new) to report vulnerabilities privately.

### What to include

- Description of the vulnerability and its potential impact
- Steps to reproduce the issue
- Affected version(s)
- Any suggested fix (optional)

### Response timeline

| Step | Target |
|------|--------|
| Initial acknowledgement | Within 7 days |
| Triage and severity assessment | Within 14 days |
| Fix or mitigation published | Within 30 days |

We will keep you informed throughout the process and credit you in the release notes (unless you prefer to remain anonymous).

## Scope

The following are **in scope** for security reports:

- **EDINET API key handling** — improper storage or exposure of `EDINET_SUBSCRIPTION_KEY`
- **Anthropic API key handling** — exposure of `ANTHROPIC_API_KEY` in logs, responses, or repository
- **File upload security** — path traversal, malicious PDF processing, or arbitrary file write via the upload endpoint
- **Authentication bypass** — circumventing the `API_KEY` environment variable check in the REST API
- **Sensitive data leakage** — real corporate disclosure data (有価証券報告書) exposed through API responses or logs
- **Dependency vulnerabilities** — critical CVEs in direct dependencies (`fastapi`, `anthropic`, `pdfplumber`, etc.)

## Out of Scope

The following are **not in scope**:

- Third-party services (EDINET, Anthropic, GitHub) — report vulnerabilities directly to those providers
- Issues reproducible only with `USE_MOCK_LLM=true` in a local development environment with no real API keys configured
- Denial-of-service via excessively large PDF uploads (resource limits are the deployer's responsibility)
- Social engineering attacks

## Security Best Practices for Deployers

- Store `EDINET_SUBSCRIPTION_KEY` and `ANTHROPIC_API_KEY` in environment variables or a secrets manager — **never** hard-code them
- Set `API_KEY` to a strong random value in production to enable authentication
- Run behind a reverse proxy (nginx, Caddy) with TLS enabled
- Keep Python dependencies up to date (`pip install --upgrade disclosure-multiagent`)
