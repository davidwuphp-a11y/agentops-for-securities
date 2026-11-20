# GitHub publication status

## Repository

- URL: https://github.com/davidwuphp-a11y/agentops-for-securities
- Owner: `davidwuphp-a11y`
- Visibility: Public
- Default branch: `main`
- Description: Evidence-grounded governance and reliability controls for AI agents in high-risk financial workflows.
- License: Apache-2.0 (LICENSE is present in the repository)

## Repository topics

Applied and visibly verified: `agentops`, `ai-governance`, `llm-agents`, `financial-services`, `securities`, `kyc`, `compliance-automation`, `auditability`, `risk-management`, `synthetic-benchmark`.

## Release inputs

Upload both files to the repository root in one commit to `main`:

- Source: `agentops-for-securities-github-ready-v5.zip` — 58,964 bytes; SHA-256 `2c92cb06ab5a65f0f37ef8598486aac263e7dc4da4974190bb6833819c1cbd86`.
- Evidence: `agentops-for-securities-evidence-bundle-v5.zip` — 1,658,882 bytes; SHA-256 `545e50512c7979e63df2fae5d20306f5725bbfb49e71411b9723610b8aefdbef`.

## Automated completion after upload

1. `.github/workflows/expand-source-archive.yml` validates the source ZIP and its 36-file SHA-256 manifest.
2. The workflow runs compile, pytest, unittest, and demo checks on Python 3.10, 3.11, 3.12, and 3.13.
3. Only after all four test jobs pass, it expands and commits the source tree to `main`.
4. `.github/workflows/publish-research-release.yml` then creates the prerelease `v0.1.0-research` and attaches both ZIP files.

## Publication state

- [x] Public repository created.
- [x] Apache-2.0 license selected and present.
- [x] Project README committed.
- [x] Release notes committed.
- [x] Repository topics applied.
- [x] Four-version test-and-expand workflow committed.
- [x] Automated prerelease workflow committed.
- [ ] Source and evidence ZIPs uploaded to the repository.
- [ ] Four-version hosted test matrix passed.
- [ ] Extracted source tree committed as browsable files.
- [ ] Research prerelease and both assets published.

The only owner action required is to upload the two v5 ZIP files through GitHub's **Add file → Upload files** page and commit them directly to `main`. The remaining validation, source expansion, and prerelease publication are configured to run automatically. Do not mark those steps complete until the workflow runs and release are visible on GitHub.

## Validation boundary

Research and engineering prototype only. Synthetic KYC/CDD examples. No real customer data, live financial decisions, production deployment, independent penetration test, WORM audit service, enterprise identity integration, or regulatory certification is claimed.
