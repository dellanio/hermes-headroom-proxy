# Contributing

Issues and pull requests are welcome at https://github.com/dellanio/hermes-headroom-proxy.
Use /issues for bugs and proposals and /compare to open a PR. Include versions,
minimal synthetic reproduction, expected/actual behavior and test output.
Never include tokens, session IDs, personal paths, raw prompts or runtime dumps.
Run `python -m unittest discover -s tests -v` and report optional skips honestly.
Add regression tests for corrections. Keep default selectors opt-in and preserve
OAuth identity, profile isolation, process ownership and fail-closed behavior.
Do not hide or bypass catalog validation failures. Replacing the private builder
rebind with a supported upstream seam is the prerequisite for catalog submission.
Original contributions are submitted under MIT. Keep attribution for third-party code.
