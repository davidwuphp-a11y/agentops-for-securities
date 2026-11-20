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

## Published source and evidence

- Source archive: `agentops-for-securities-github-ready-v5.zip` (58,964 bytes).
- Evidence bundle: `agentops-for-securities-evidence-bundle-v5.zip` (1,658,882 bytes).
- Both files are attached to the GitHub prerelease `v0.1.0-research`.
- The source archive was integrity-checked, its 36 manifest-tracked files were SHA-256 verified, and the source tree was expanded into browsable repository files.

## Hosted validation

- Archive validation and source expansion workflow: successful.
- Python 3.10, 3.11, 3.12, and 3.13: all hosted jobs passed.
- Each matrix job completed compilation, pytest, unittest discovery, and deterministic demo.
- The separate repository test workflow also passed on all four Python versions.
- The first source-expansion attempt failed because the GitHub App token lacked permission to push a workflow file. The workflow was adjusted to preserve the repository's workflow files, and the subsequent expansion succeeded. An initial test workflow run occurred before the source tree existed and failed; a fresh run after expansion passed all four jobs.

## Publication state

- [x] Public repository created.
- [x] Apache-2.0 license selected and present.
- [x] README, architecture, security, contribution, provenance, test, and phase documentation committed.
- [x] Repository topics applied.
- [x] Source and evidence ZIPs uploaded.
- [x] Source archive and manifest hashes validated in GitHub Actions.
- [x] Source tree committed as browsable files.
- [x] Python 3.10–3.13 hosted validation passed.
- [x] Research prerelease and both assets published.

## Release

- Tag: `v0.1.0-research`
- Title: `AgentOps for Securities v0.1.0 — Research Prototype`
- Release: https://github.com/davidwuphp-a11y/agentops-for-securities/releases/tag/v0.1.0-research

## Validation boundary

Research and engineering prototype only. Synthetic KYC/CDD examples. No real customer data, live financial decisions, production deployment, independent penetration test, WORM audit service, enterprise identity integration, or regulatory certification is claimed.
