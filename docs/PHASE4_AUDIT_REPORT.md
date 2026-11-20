# Phase 4 Source Audit and Remediation Report

Date: 2026-11-19
Input artifact: `agentops-for-securities-phase4(3).zip`
Input SHA-256: 03cf0a0e167ae626741a36ad63108884083c3a57ba6daf695214f8ed0de1ed29

## Scope and method

The uploaded ZIP was opened and extracted. Its archive integrity check (`ZipFile.testzip`) returned `None`. All 15 archive members were enumerated. Source review covered the core workflow store, runtime, reliability ledger, tests, README, architecture and Phase 4 report. Tests and demo were executed locally in the available Python environment.

## Baseline validation

- Baseline pytest: 29 passed.
- Baseline runtime: 0.15 seconds.
- Baseline archive integrity: passed.

## Findings and changes

### F-01 — Approval queue could be entered without policy-gate enforcement
**Severity:** High  
**Evidence:** `Store.transition` originally permitted `IN_REVIEW -> PENDING_APPROVAL` based only on the transition table. `PolicyGate.evaluate_for_approval` was a separate helper and was not invoked by that transition.  
**Remediation:** The transition now evaluates the gate before allowing `PENDING_APPROVAL`.

### F-02 — Evidence/findings remained mutable after submission
**Severity:** High  
**Evidence:** `add_evidence` and `add_finding` originally did not restrict writes when a case was pending approval or terminal. This allowed the evidence basis to change after submission/decision.  
**Remediation:** Evidence and findings are now frozen in `PENDING_APPROVAL` and terminal states.

### F-03 — Case transition read/write race
**Severity:** High  
**Evidence:** The original transition read the case, checked its version, then updated without a transaction or conditional version predicate. Concurrent writers could act on a stale read.  
**Remediation:** Transitions now serialize with `BEGIN IMMEDIATE` and update with a version predicate.

### F-04 — Remaining identity and execution guarantees are prototype-level
**Severity:** High / residual  
**Evidence:** Maker/checker are caller-supplied strings, not identities authenticated by an IdP; the local SQLite ledger has no lease/heartbeat or fencing token; external tools must enforce the supplied idempotency key; model output has no general JSON Schema validator; the provider adapter was tested only with mocked transport.  
**Remediation:** Not claimed fixed in this audit. These remain Phase 5+ work and are listed as explicit limitations.

## Post-remediation validation

- `pytest -q`: 31 passed.
- `python -m unittest discover -s tests -v`: 31 tests, OK.
- `python -m compileall -q agentops tests`: exit code 0.
- `python -m agentops.demo`: exit code 0; demo reached `APPROVED`, policy gate allowed, audit chain valid.
- The Python host emitted an unrelated spreadsheet-runtime warmup warning during startup; it did not change the command exit codes or test outcomes.

## Residual limitations

- No production identity provider or authenticated maker/checker identities.
- No lease/heartbeat recovery, fencing token, or distributed worker coordination.
- No exactly-once guarantee for external side effects; a downstream tool must durably deduplicate the idempotency key.
- No uncertainty-aware recovery state for a timeout after a remote side effect.
- No general fail-closed JSON Schema validator or immutable prompt/policy version registry.
- No benchmark corpus, adversarial evaluation suite, signed/WORM audit storage, or production deployment.
- OpenAI-compatible adapter has only mock-transport tests; no live provider request was made.

## Release posture

This package is an engineering prototype only. It is not production-certified and must not be used with real customer data or live financial decisions.
