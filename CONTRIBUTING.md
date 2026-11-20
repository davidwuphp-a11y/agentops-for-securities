# Contributing

Thanks for considering a contribution.

## Development setup

- Python 3.10+
- Runtime uses the Python standard library.
- Install the test runner with `python -m pip install -r requirements-dev.txt`.

## Before submitting

```bash
python -m compileall -q agentops benchmarks tests
python -m pytest -q
python -m unittest discover -s tests -q
python -m agentops.demo
```

## Contribution requirements

- Use synthetic data only. Never commit customer records, credentials, API keys, tokens, or private logs.
- Add regression tests for security and reliability changes.
- Do not weaken fail-closed behavior or silently retry ambiguous external side effects.
- Document any changed guarantee, assumption, threat, or limitation.
- Keep benchmark ground truth and runtime behavior separate; do not use an LLM judge to override deterministic safety failures.
- Avoid claims of regulatory certification or production readiness.

By submitting a contribution, you agree that your contribution may be distributed under the repository's license once selected by the maintainers.
