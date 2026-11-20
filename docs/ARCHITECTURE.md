# Phase 2 Architecture

```text
Business Workflow
      |
      v
Workflow Runtime ---- optimistic version checks ---- SQLite Store
      |                                          |-- cases / evidence / findings
      |                                          |-- approvals / tool_runs
      |                                          `-- hash-chained events
      v
Policy Gate ---- verified evidence + finding requirements
      |
      v
Tool Registry ---- RBAC allow-list ---- Tool Adapter
      |
      v
Human Maker-Checker Approval
      |
      v
Replay / Audit Verification
```

## Security invariants
1. A finding cannot cite evidence from another case.
2. A finding cannot be recorded without at least one evidence reference.
3. Policy gate fails closed when mandatory verified evidence is missing.
4. Tool execution requires a matching principal role.
5. Maker and checker must be different principals.
6. Terminal cases cannot transition further.
7. Event-chain verification detects payload/order/previous-hash tampering.

## Next engineering increments
- Transaction boundaries and idempotency keys for every command.
- Signed audit checkpoints and external append-only storage.
- OPA/Rego or a versioned internal policy DSL.
- Durable async orchestration, retries, leases and dead-letter queue.
- OpenTelemetry-compatible traces and provider-neutral LLM adapters.
- Dataset schema, evaluator suite, adversarial test harness and cost/latency benchmark.
