# Hermes Headroom Proxy (v0.3.0, experimental)

> **Independent community project, NOT accepted into the Hermes plugin catalog.**
> Native Anthropic integration uses a **private API / core builder rebind** and
> fails the catalog's rule 9 (no core override), even when disabled by default.
> Do not treat this repository as an official or catalog-approved integration.
> An official extension hook is requested upstream; no catalog PR is submitted.

Headroom lifecycle management, diagnostics, CCR retrieval and opt-in child routing
for Hermes. Corrections, issues and pull requests are welcome.

## Integration boundary and limitations

- Public plugin surfaces: `ctx.register_tool`, `ctx.register_command`,
  `ctx.register_cli_command`, `ctx.register_hook`, `ctx.on_unload` and
  `ctx.get_config`. Lifecycle uses `on_session_start` plus plugin discovery.
- `auto_claude_cli` uses the public `pre_tool_call` hook for recognized plain
  Bash `claude` terminal commands. It preserves original argument text and
  scopes environment changes to a child. Recognized bypass forms are refused.
  This is **not a shell sandbox**: nested scripts, dynamic executables,
  PowerShell, subprocesses in unrelated tools and arbitrary shell grammar are
  not covered. Use the explicit launcher for unsupported forms.
- `native_anthropic` (default false) rebinds
  `agent.anthropic_adapter.build_anthropic_client`. It first constructs the
  original first-party client, then attaches a request URL redirection hook
  after OAuth/identity construction. This private seam is version-sensitive,
  in-process only, and **not catalog compliant**. Existing clients are not
  retrofitted. Unload restores the builder and deactivates old hooks.
- No native Hermes Codex OAuth interception or automatic routing of other
  providers is implemented. Explicit API-key child launchers are separate.
- Subscription launching refuses API-key/cloud/custom endpoint overrides;
  it does not certify your subscription tier, billing policy or provider terms.
- Claude custom BASE_URL disables Remote Control on Claude Code 2.1.196+;
  tool-search and 1M behavior remain client/version dependent. No 1M tier is forced.
- No Electron-window-open autostart guarantee, plugin-host isolation guarantee,
  compression savings claim or universal transparent routing claim.
- A healthy proxy does not prove a request traversed it. Existing external
  services are reused only after verification and are never stopped by cleanup.
  Only this host's owned process is eligible for shutdown.

## Setup (opt-in, review before enabling)

Requires Python >=3.10, a separately installed Headroom executable on PATH,
and Hermes for native plugin surfaces. This package does not vendor Headroom.
From a reviewed checkout:

```bash
python -m pip install .
hermes-headroom-proxy --help
```

For Hermes plugin installation use the documented Git source workflow with
repository `https://github.com/dellanio/hermes-headroom-proxy` and subdirectory
`headroom_proxy`; pin the exact reviewed commit rather than following main.
See [official plugin documentation](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins).
Installation/discovery can start Headroom because `autostart` defaults true.
Set `autostart` false in plugin settings before enabling if you only want diagnostics.
The portable JSON in `examples/claude-subscription.json` is a settings object
under `plugins.entries.headroom_proxy.settings`, **not a complete Hermes config**.
Configure via the official Hermes settings commands/UI, not by replacing config.yaml.
No example contains credentials or machine-specific executable paths.

```bash
hermes headroom-proxy --help
hermes headroom-proxy status
hermes headroom-proxy diagnose
```

Explicit `claude` and `run-api` subcommands require their respective opt-in
selectors (`claude_cli` and `providers`/`models`). Automatic selectors are
independent and default false. Automatic covered routes fail closed;
`warn-direct` applies only to explicit child launching.

Rollback: disable `native_anthropic` and `auto_claude_cli` through Hermes
plugin settings, unload/disable the plugin and start fresh sessions. Existing
SDK clients may require a new process; do not assume live clients are replaced.
No installer in this repository edits global Claude/Codex settings.

## Validation

```bash
python -m unittest discover -s tests -v
hermes plugins validate ./headroom_proxy --install-deps
```

The default suite has two optional integration tests, selected by
`HERMES_TEST_SOURCE` (Hermes checkout, with isolated `HERMES_HOME`) and
`HEADROOM_TEST_EXECUTABLE` (Headroom executable). Skips are not passes.
See [AUDIT.md](AUDIT.md) for the sanitized publication audit and actual results.
**Catalog validation is expected to fail no-core-override; do not submit this tree.**

## Community and licensing

[Report a bug or request an improvement](https://github.com/dellanio/hermes-headroom-proxy/issues).
[Pull requests](https://github.com/dellanio/hermes-headroom-proxy/pulls) are welcome;
read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
MIT for original project code, copyright Dellanio Alencar.
Contact: contato@dellanio.com. Third-party components retain their own licenses;
see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
