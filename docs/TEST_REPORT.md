# Test Report — Phase 5 Integrated / Phase 6 Benchmark v1

Date: 2026-11-19

| Check | Result |
|---|---:|
| pytest | 64 passed; 4 parameterized subtests |
| unittest discovery | 64 passed |
| compileall (`agentops benchmarks tests`) | Passed |
| Synthetic demo | Passed; case APPROVED; audit chain valid |
| Benchmark size | 200 cases |
| Benchmark split | 120 train / 40 validation / 40 test |
| Concurrent lease workers | 8 contenders; exactly 1 acquisition succeeds |
| ZIP integrity | Verified after packaging |
| Clean extraction test | Required before release handoff |

No live model API, paid service, real customer data, or production financial action was used in these tests.
