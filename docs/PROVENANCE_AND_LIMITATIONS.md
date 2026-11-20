# Provenance, Version Retention, and Limitations

## Version lineage retained in the evidence bundle

1. `agentops-for-securities-phase4(3).zip` — user-provided Phase 4 source archive; retained unchanged.
2. `agentops-for-securities-phase4-audited-v1.zip` — prior Phase 4 audit/fix snapshot; retained unchanged.
3. `agentops-for-securities-phase5-foundations-v1.zip` — prior Phase 5 foundations snapshot; retained unchanged.
4. `agentops-for-securities-phase5-integrated-phase6-benchmark-v1.zip` — retained prior increment with lease-coordinated execution, approval snapshot binding, stricter schema meta-validation, and synthetic benchmark v1.
5. `agentops-for-securities-phase5-integrated-phase6-benchmark-v2.zip` — current increment adds monotonic fencing across lease release, runtime schema enforcement, Prompt/Policy registry binding, and Phase 7 regression coverage.

Each artifact is checksummed in the evidence manifest. Earlier versions are not overwritten.

## What was actually run for the current increment

- Full pytest suite: 64 passed, plus 4 parameterized subtests.
- Full unittest discovery: 64 passed.
- Python compileall over `agentops`, `benchmarks`, and `tests`.
- Demo run: simulated case reached APPROVED; policy gate passed; audit chain verified.
- Benchmark structure check: 200 cases with 120/40/40 split.
- ZIP integrity check and clean extraction/re-test are part of release verification.

## Explicit limitations

- This is a research and engineering prototype, not a production financial control system.
- Only synthetic case data is included. Do not use real customer information or live financial decisioning.
- The OpenAI-compatible adapter has not been validated against a live provider in this release.
- The downstream system must enforce idempotency keys and fencing tokens; this repository cannot enforce behavior inside third-party services.
- Ambiguous external side effects require operator reconciliation. No exactly-once guarantee is made.
- Maker/checker identities are string labels in the prototype; production authentication and authorization integration remain required.
- Hash chains and approval digests are tamper-evident checks, not digital signatures or WORM storage.
- The benchmark is synthetic and rule-generated. Its test split is included and is not blind; no external adjudication, inter-rater study, contamination study, or real-world validity claim is made.
- No regulatory certification, legal opinion, penetration test, production deployment, or independent security audit is claimed.

## User authorization boundary

No GitHub repository was created and no code was pushed. Publishing this project to a public repository requires the user's explicit authorization.
