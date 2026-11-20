# Phase 7 Security and Reliability Regression Report

Date: 2026-11-19
Status: Initial deterministic regression matrix implemented; not a complete independent security assessment.

## Controls exercised by automated tests

| Area | Test evidence | Result |
|---|---|---|
| Role-based tool access | Agent/tool RBAC denial tests | Pass |
| Tool allowlist | Full plan validated before tool execution | Pass |
| Output contract | Schema rejection before side-effecting tool invocation | Pass |
| Evidence isolation | Cross-case evidence citation rejected | Pass |
| Approval gate | Missing verified evidence blocks submission | Pass |
| Maker-checker | Same principal cannot approve own work | Pass |
| Approval integrity | Evidence/findings/policy/decision digest mutation detected | Pass |
| Audit integrity | Modified event payload invalidates hash chain | Pass |
| Lease contention | Eight concurrent SQLite workers; exactly one acquires active lease | Pass |
| Fencing monotonicity | Release preserves counter; subsequent acquisition increments token | Pass |
| Stale worker | Expired lease takeover prevents stale result commit | Pass |
| Ambiguous side effect | Tool timeout after invocation quarantines step for reconciliation | Pass |
| Schema fail-closed | Unsupported nested/unreached keywords rejected | Pass |

## Important unvalidated threats

- No real model was used to execute adversarial prompt-injection documents. The benchmark contains injection scenarios, but this is not a live model robustness result.
- No destructive process-kill / power-loss test was performed against a production-like database or external system.
- No independent penetration test, fuzzing campaign, dependency audit, or red-team review was performed.
- The local hash chain and approval digest are not signed, externally anchored, or stored in WORM infrastructure.
- Authentication and authorization still rely on prototype-level principal labels; no enterprise identity provider is integrated.
- Downstream services must enforce idempotency and fencing tokens. This cannot be guaranteed by the local executor alone.
- No live provider call or paid API was used to validate the model adapter.

## Conclusion

The included checks demonstrate specific local prototype invariants only. They do not establish production readiness, regulatory compliance, or resistance to all adversarial behavior.
