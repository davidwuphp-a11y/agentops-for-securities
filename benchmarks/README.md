# AgentOps Synthetic Benchmark v1

This benchmark contains 200 deterministic synthetic KYC/CDD cases. It is an engineering benchmark, not a regulatory test, and does not contain real customer data.

| Category | Cases |
|---|---:|
| Normal due diligence | 30 |
| Identity conflict | 25 |
| UBO complexity | 30 |
| Evidence missing | 25 |
| Rule conflict | 20 |
| Prompt injection | 25 |
| High-risk customer | 25 |
| Audit/replay | 20 |
| **Total** | **200** |

Split: 120 train / 40 validation / 40 test. The split is deterministic and stratified within each category. The test split is held out by convention only; it is included in this repository and is not secret or blind.

Run:

```bash
python benchmarks/generate_benchmark.py
python -m unittest discover -s tests -p test_benchmark.py -v
```

The evaluator in `evaluate.py` is deterministic and does not use an LLM judge. A production-quality independent evaluator, adjudicated labels, inter-rater review, external benchmark comparison, and contamination controls remain future work. Metrics are descriptive and should not be interpreted as proof of real-world compliance or model safety.
