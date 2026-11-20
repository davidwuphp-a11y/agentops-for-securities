# Phase 5 Integration Report

Date: 2026-11-19
Status: Integrated engineering increment; production hardening remains incomplete.

## Implemented

1. **Leased execution coordinator**: `LeasedResumableExecutor` acquires a SQLite lease per run step and passes the fencing token plus stable idempotency key to the downstream tool adapter.
2. **Ambiguous outcome quarantine**: once an external tool has been invoked, any exception or missing committed result moves the step to `RECONCILIATION_REQUIRED`. The executor does not silently retry it.
3. **Expired worker recovery**: `quarantine_expired_running()` finds RUNNING steps whose lease is absent or expired and moves them to reconciliation. It does not assume the external side effect did not occur.
4. **Explicit reconciliation**: `resolve_reconciliation()` requires operator-supplied evidence and either confirms an applied outcome with an output object or confirms non-application before making the step retryable.
5. **Approval snapshot binding**: approval rows now store a SHA-256 digest over the case ID, decision, evidence metadata/digests, findings, and policy version set. `verify_approval_snapshot()` detects out-of-band changes.
6. **Schema meta-validation**: the supported JSON Schema subset is recursively checked before validating data, including unused properties and empty-array item schemas. Unsupported keywords and malformed keyword values fail closed.
7. **Runtime output contract**: `AgentSpec.output_schema` is validated before any tool execution; invalid output prevents all side effects in the plan.
8. **Prompt/Policy runtime binding**: optional registered Prompt and Policy name/version pairs are verified before model invocation, and their registry digests plus the active prompt digest are recorded in the agent-run audit input.

## Tests added

- Leased execution passes the fencing token to the tool.
- Expired RUNNING steps are quarantined rather than replayed.
- Reconciliation requires evidence and distinguishes confirmed-applied from confirmed-not-applied.
- Stale worker takeover prevents stale result commit.
- Tool timeout after a possible downstream side effect enters reconciliation.
- Approval digest binds the decision and policy versions; mutation is detected.
- Unsupported keywords in unreachable schema branches are rejected.

## Semantics and limitations

- A fencing token is useful only if the downstream resource enforces it. The included prototype passes the token but cannot force a third-party API to reject stale tokens.
- SQLite transactions do not create an atomic transaction with external systems. Idempotency keys must be persisted downstream or an outbox/inbox protocol must be used.
- Reconciliation is an explicit operator workflow, not automatic proof of whether a side effect occurred.
- Maker/checker values are distinct labels in this prototype; a production identity provider and authenticated principal binding are still required.
- Approval digest detects data mutation when checked; it is not a digital signature and the local SQLite file is not tamper-proof/WORM storage.
- Prompt and policy registry lookups are optional until the caller configures a registry and supplies the version fields; production policy governance still needs authenticated release controls.
- The schema validator implements a deliberately limited subset, not full JSON Schema Draft 2020-12.

## Validation

Current full suite: 59 pytest tests passed (plus 4 parameterized subtests). Standard-library unittest discovery, compileall, and the synthetic demo are also run as release checks.
