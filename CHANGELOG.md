# Changelog

## GitHub publication preparation — 2026-11-20
- Finalized repository README and publication-state documentation.
- Added the Apache-2.0 license to the source archive.
- Applied and verified the repository description and ten GitHub topics.
- Source archive upload, hosted CI verification, and GitHub Release remain pending owner-side archive upload.


## GitHub publication preparation — 2026-11-19
- Added least-privilege GitHub Actions CI matrix for Python 3.10–3.13.
- Added CONTRIBUTING.md, SECURITY.md, research release notes, and publication metadata/checklist.
- No license selected; public repository creation/upload still requires owner authorization.

## Phase 5 integrated v2 / Phase 6 benchmark v1 / Phase 7 regression increment — 2026-11-19
- Integrated lease coordination with resumable execution and fencing-token propagation.
- Added reconciliation quarantine for expired RUNNING tasks and ambiguous external tool outcomes; no automatic retry until explicit evidence-based resolution.
- Bound approval records to a SHA-256 snapshot of case evidence, findings, policy versions, and decision.
- Added recursive fail-closed schema meta-validation, including unused nested schema branches.
- Added 200 deterministic synthetic KYC/CDD benchmark cases with 120/40/40 split and a deterministic evaluator.
- Added regression and benchmark tests; 64 pytest tests pass plus 4 parameterized subtests.
- Preserved monotonically increasing fencing tokens across explicit lease release.
- Integrated output schema validation and Prompt/Policy digest binding into Agent Runtime.
- Added concurrent lease acquisition and ambiguous-side-effect regression tests.

## Phase 5 foundations — 2026-11-19
- Added SQLite lease ledger with expiry takeover, heartbeat, owner checks, and fencing tokens.
- Added strict JSON Schema subset validator and immutable Prompt/Policy version registry.

## Phase 4 audited v1 — 2026-11-19
- Fixed approval-gate and evidence-freeze gaps, and hardened state transitions with transactional compare-and-swap.
- Added source audit report and clean-room release verification.
