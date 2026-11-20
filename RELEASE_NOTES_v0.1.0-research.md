# AgentOps for Securities v0.1.0-research

Research and engineering prototype release.

## Included

- Evidence-grounded KYC/CDD workflow primitives and policy gate.
- Hash-linked audit events and replayable tool-call records.
- Role checks, tool allowlists, evidence isolation, and maker-checker separation.
- SQLite execution ledger with idempotency keys and bounded retries.
- Lease-coordinated execution, fencing-token propagation, and explicit reconciliation for ambiguous external effects.
- Immutable Prompt/Policy version registry, runtime digest binding, and fail-closed output-schema validation.
- 200-case synthetic benchmark and deterministic evaluator.
- Regression tests and CI workflow.

## Validation snapshot

- 64 tests passed in pytest and unittest discovery, plus four parameterized subtests.
- Clean-room extraction and re-test passed.
- Compilation and demo execution passed.
- Manifest SHA-256 verification passed.
- Secret-pattern scan found no matches for the checked credential formats.

## Limitations

Not production-certified. No real customer data or live financial decisioning. No exactly-once external side-effect guarantee. No live model-provider validation, independent penetration test, WORM audit storage, enterprise identity integration, or regulatory certification. The included benchmark test split is not secret or blind.
