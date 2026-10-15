# Security

Report vulnerabilities privately to contato@dellanio.com. Do not post credentials
or sensitive runtime evidence in public issues or PRs. Include a minimal synthetic
reproducer, affected version and impact. No response-time SLA is promised.

This experimental plugin handles requests containing credentials and prompt data.
Use only a trusted local Headroom process; loopback alone is not authentication.
Native integration uses private Hermes APIs and is not catalog approved.
Bash matching is routing convenience, not a security boundary. Review code and
pin a commit before installing. Never expose the proxy port publicly.
