# Phase 6 Benchmark v1 Report

Date: 2026-11-19
Status: Synthetic benchmark v1 generated; not an externally validated benchmark.

## Dataset

200 deterministic synthetic KYC/CDD cases:

- Normal due diligence: 30
- Identity conflict: 25
- UBO complexity: 30
- Evidence missing: 25
- Rule conflict: 20
- Prompt injection: 25
- High-risk customer: 25
- Audit/replay: 20

Stratified split: 120 train / 40 validation / 40 test. The test split is included in the repository and is therefore held out by convention only, not secret or blind.

Dataset: `benchmarks/data/agentops_synthetic_benchmark_v1.json`
SHA-256: `3534065b19b6d10b91fa1097c7944178714cbc6eb1ad0a9b6c4318c516577075`

## Evaluator

`benchmarks/evaluate.py` is deterministic and independent of model runtime code. It requires exact case-ID coverage and reports decision accuracy, unsafe approval rate, policy violation rate, injection success rate, evidence precision/recall, escalation precision/recall, replay consistency, and over-refusal rate. It does not use an LLM judge.

## Limitations

- Labels and scenarios are generated from explicit rules; no external compliance experts have adjudicated them.
- No human inter-rater agreement study has been performed.
- No external benchmark comparison or contamination study has been performed.
- No live customer data, real counterparties, or production decision flows are included.
- A perfect score on this dataset is not evidence of production safety, regulatory compliance, or generalization.
