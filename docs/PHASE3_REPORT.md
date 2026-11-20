# Phase 3 Engineering Report — Agent Runtime & Evidence Graph

Date: 2026-11-18

## Delivered
1. Provider-neutral model adapter protocol and deterministic fixture adapter.
2. Agent runtime with principal role enforcement, tool allowlists, maximum step budget, case-scoped evidence citation checks, trace collection and persisted run records.
3. Full tool-plan validation before execution, so a malformed or over-budget plan is rejected before any tool is invoked.
4. Evidence graph projection connecting evidence records to findings.
5. Deterministic evaluator for expected-vs-actual conclusion, evidence precision and unsupported evidence references.

## Verification
- Command: `python -m unittest discover -s tests -v`
- Result: 20 tests passed.
- Coverage includes legacy persistence/workflow/policy/audit/RBAC tests and new runtime allowlist, role, evidence isolation, step-budget, evidence graph and evaluation tests.

## Demonstrated limitations
- The model is a deterministic fixture, not a live provider integration.
- Evaluation is a small deterministic harness, not a statistically validated benchmark.
- EvidenceGraph is an export projection, not yet a graph database or temporal provenance engine.
- Runtime tool calls are sequential and local; no distributed queue, sandbox, timeout isolation or transactional side-effect protocol yet.
- SQLite hash chaining detects alteration within the retained chain but is not equivalent to signed, externally anchored WORM audit storage.

## Next engineering priorities
1. Add idempotency keys and durable run/step state to support crash recovery.
2. Add provider adapter with structured-output validation, timeout and retry policy; keep credentials outside source code.
3. Add a synthetic case benchmark with adjudicated expected outcomes and adversarial cases.
4. Add temporal provenance, policy version pinning and deterministic replay snapshots.
5. Add API layer and operator dashboard only after runtime semantics stabilize.
