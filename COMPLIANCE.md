# Compliance & Security Report

This file summarises the security and compliance checks (SocChecks) for the
JOSS submission readiness of **neural-harness**. Reports are regenerated
automatically by the [Security Audit workflow](../blob/main/.github/workflows/security.yml)
on every push/PR and weekly, then committed under [`compliance/`](./compliance/).

## A. SocCheck register

| # | Check | Tool | Status | Evidence |
|---|-------|------|--------|----------|
| A1 | SBOM (CycloneDX) | `cyclonedx-py` | ✅ Generated on CI | `compliance/sbom.cyclonedx.json` |
| A2 | License scan / conflict detection | `licensecheck` | ✅ Generated on CI | `compliance/license-report.json` |
| A3 | Vulnerability scan (CVEs) | `pip-audit --strict` | ✅ Generated on CI | `compliance/vuln-report.json` |
| A4 | Secret detection (leaked keys/tokens) | `gitleaks` | ✅ CI gate on push/PR + scheduled | `.github/workflows/security.yml` |
| A5 | Dependency pinning | `pyproject.toml` | ✅ Trivially met — stdlib-only, `dependencies = []`; dev deps ranged (`pytest>=7`) | `pyproject.toml` |
| A6 | Supply-chain provenance | `sigstore` / `in-toto` | ⏳ Planned for first tagged release | Release attestation |
| A7 | `COMPLIANCE.md` | Manual | ✅ This document | `COMPLIANCE.md` |
| A8 | `security.yml` CI workflow | GitHub Actions | ✅ Added | `.github/workflows/security.yml` |

## B. Dependency obligations

- **Runtime dependencies:** none (Python 3 standard library only) — no
  transitive supply-chain surface for production use.
- **Development dependencies:** `pytest>=7` (ranged). Used by CI only.
- **Tooling CI dependencies:** `cyclonedx-bom`, `pip-audit`, `licensecheck`
  (pinned to latest release at run time; tracked via Dependabot).

## C. Known findings & mitigations

- **A2/A3:** any license conflicts or CVEs flagged by the CI jobs must be
  resolved before the JOSS pre-submission checklist is signed off. Historical
  scans are archived under `compliance/` for reviewer inspection.
- **Secrets:** gitleaks runs over full history on every push. The public
  history is clean as of the most recent run.

## D. Compliance obligations

1. Do not merge PRs that fail the Safety gates (gitleaks, pip-audit).
2. Re-run and commit `compliance/` reports before each tagged release.
3. On the first tagged release, sign the release artifact with Sigstore
   (A6) and record provenance after the attestation completes.
4. Reference this file and `compliance/` outputs as the TRL-justification
   evidence in any grant/ethics submission.

> Generated: 2026-09-25. Review cadence: re-run Section A with every release.