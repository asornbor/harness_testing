# Cloud coding-harness benchmark

This branch is the clean implementation of a reproducible benchmark comparing Codex CLI, Claude Code, Pi, Crush, and OpenCode while targeting the same OpenAI subscription model through CLIProxyAPI.

Heavy installation, Docker execution, Go binaries, and validation run in GitHub Codespaces or GitHub Actions. The repository never stores OAuth credentials. Subscription calls are disabled in CI.

Implementation is being delivered in verified milestones. The first milestone resolves an immutable npm lock for genuine upstream harness packages; it does not substitute local wrapper executables.
