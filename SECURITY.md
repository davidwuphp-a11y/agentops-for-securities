# Security Policy

## Scope

AgentOps for Securities is a research and engineering prototype. It is not approved for real customer data, live financial decisions, or production compliance workflows.

## Reporting a vulnerability

Please do not publish credentials, personal data, exploitable details, or sensitive customer information in public issues. If GitHub private vulnerability reporting is enabled for this repository, use it. Otherwise contact the repository owner through the contact method on the owner's GitHub profile and include a minimal reproduction without sensitive data.

## Response expectations

This is a best-effort research project, not a supported commercial service. There is no guaranteed response or remediation SLA.

## Known security limitations

See `docs/PHASE7_SECURITY_REPORT.md` and `docs/PROVENANCE_AND_LIMITATIONS.md`. In particular, downstream systems must enforce idempotency keys and fencing tokens; local hash chains are not WORM storage; identity-provider integration and independent security review are not implemented.
