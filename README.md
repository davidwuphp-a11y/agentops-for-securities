# AgentOps for Securities

**An evidence-grounded governance and reliability control plane for AI agents in high-risk financial workflows.**

AgentOps for Securities is a research and engineering prototype for controlling how AI agents interact with evidence, policies, human approvals, and external tools in a simulated securities KYC/CDD workflow.

> **Project status:** Research and engineering prototype. Not production-certified and not approved for real customer data or live financial decisions.

## What it demonstrates

- **Evidence-grounded decisions:** structured case evidence, evidence references, findings, and policy-gated decisions.
- **Tool governance:** role checks, explicit action allowlists, and separation between proposing and executing actions.
- **Maker-checker controls:** approval records bound to a SHA-256 snapshot of evidence, findings, policy versions, and the decision.
- **Tamper-evident audit trail:** hash-linked audit events and replayable tool-call records.
- **Durable orchestration:** SQLite-backed run/step ledger, stable idempotency keys, bounded retries, and restart scanning.
- **Lease coordination:** expiry, heartbeat, owner checks, monotonically increasing fencing tokens, and concurrent-worker protection.
- **Ambiguous-outcome safety:** uncertain external side effects are quarantined for reconciliation rather than blindly retried.
- **Version and schema controls:** immutable Prompt/Policy digests and fail-closed JSON Schema subset validation.
- **Synthetic evaluation:** 200 deterministic synthetic KYC/CDD cases, a 120/40/40 split, and a deterministic evaluator.

## Repository map

| Path | Purpose |
|---|---|
| `agentops/` | Workflow, policy, audit, runtime, lease, and reliability implementation |
| `tests/` | Unit, integration, regression, reliability, and benchmark tests |
| `benchmarks/` | Synthetic benchmark data, generator, evaluator, and protocol |
| `docs/` | Architecture, phase reports, test evidence, provenance, and limitations |
| `.github/workflows/` | CI test workflow |

## Quick start

Python 3.10+.

```bash
python -m pip install -r requirements-dev.txt
python -m compileall -q agentops benchmarks tests
python -m pytest -q
python -m unittest discover -s tests -q
python -m agentops.demo
```

The core workflow uses the Python standard library. Development tests use the dependencies in `requirements-dev.txt`.

## Validation snapshot

The v0.1.0 research package records **64 passing tests** (plus four parameterized subtests), clean-room extraction/re-test, compilation, demo execution, and SHA-256 manifest verification. See [TEST_REPORT.md](docs/TEST_REPORT.md), [PROVENANCE_AND_LIMITATIONS.md](docs/PROVENANCE_AND_LIMITATIONS.md), and the phase reports for scope and caveats. CI is configured in GitHub Actions; a green local test report is not a substitute for a completed hosted CI run.

## Safety and reliability boundaries

- The KYC/CDD process and all benchmark records are synthetic reference material, not an actual firm's internal SOP or customer workflow.
- No real customer data, live financial decisions, or paid model-provider requests were used for validation.
- The provider adapter is tested with mocked transport; no claim of live provider integration is made.
- Durable local orchestration does **not** guarantee exactly-once external side effects. Downstream tools must implement idempotency or an outbox/inbox protocol.
- SQLite WAL is for local development, not a distributed production queue.
- Ambiguous external outcomes require explicit reconciliation; automatic retries can duplicate side effects.
- The benchmark is deterministic and synthetic; its evaluation split is not secret or blind.

A production deployment would still require, at minimum, enterprise identity and authorization, PostgreSQL or equivalent transactional storage, queue isolation, secrets management, signed/WORM audit retention, observability, backups and disaster-recovery tests, independent penetration testing, and formal security/compliance review.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Phase 3 report](docs/PHASE3_REPORT.md)
- [Phase 4 audit report](docs/PHASE4_AUDIT_REPORT.md)
- [Phase 5 foundations](docs/PHASE5_FOUNDATIONS_REPORT.md)
- [Phase 5 integration](docs/PHASE5_INTEGRATION_REPORT.md)
- [Phase 6 benchmark](docs/PHASE6_BENCHMARK_REPORT.md)
- [Phase 7 security regression report](docs/PHASE7_SECURITY_REPORT.md)
- [Test report](docs/TEST_REPORT.md)
- [Provenance and limitations](docs/PROVENANCE_AND_LIMITATIONS.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Research release notes](RELEASE_NOTES_v0.1.0-research.md)

## License

Licensed under the [Apache License 2.0](LICENSE).
