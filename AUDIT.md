# Sanitized publication audit

This is a fresh export of original project source and tests, not a mirror of the
private development Git history. Personal runtime evidence, session identifiers,
local installation reports and machine-specific diagnostic scripts were excluded.
The original local repository/history and installed plugin were left unchanged.

The native integration in `headroom_proxy/transparent.py` rebinds the core
Anthropic builder. It is explicitly experimental and violates catalog rule 9.
Disabled defaults do not remove the static admission blocker. No catalog PR.

No live inference, subscription-tier, compression-savings, Desktop-restart or
plugin-host-isolation certification is made by this publication audit.
Test and validator results are recorded below after real execution.

## Executed publication validation

- Python 3.14 unittest discovery: 42 collected, 40 passed, 2 optional integration tests skipped (native host and real Headroom lifecycle were not enabled).
- Official Hermes validator with --install-deps --json: exit 1, ok=false. All reported checks except no core override passed; static security scan safe. Rule 9 identifies builder assignment and restoration in transparent.py.
- Warning: conditional pre_tool_call absent in default capability probe; isolation verdict in_process, host_ready=false. No live inference or restarts performed.
- Fresh export scan found no matching credential-token/private-key/JWT/session-ID/personal-path patterns. This bounded automated scan is not a guarantee that every possible secret can be detected.
