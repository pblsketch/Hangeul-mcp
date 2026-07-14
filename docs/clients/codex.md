# Codex

Verified against current official Codex MCP docs on **2026-07-12**.

- Official sources:
  - https://developers.openai.com/codex/mcp/
  - https://learn.chatgpt.com/docs/extend/mcp?surface=cli
  - https://learn.chatgpt.com/docs/config-file/config-reference
- Confidence: **high**
- Exact schema verified: **TOML `[mcp_servers.hangeul-mcp]`**
- Official config surfaces verified:
  - Global: `~/.codex/config.toml`
  - Project-local: `.codex/config.toml`
- Official manual management commands verified:
  - `codex mcp list`
  - `codex mcp get hangeul-mcp`
  - `codex mcp add hangeul-mcp -- <command> [args...]`
  - `codex mcp remove hangeul-mcp`

## Recommended setup

```bash
hangeul-mcp-manage setup --client codex
hangeul-mcp-manage doctor
```

This repository currently auto-manages only the global `~/.codex/config.toml`. If project-local `.codex/config.toml` already exists, setup fails closed and returns manual scope guidance instead of silently picking one.

Managed installs currently register a stable launcher command as an absolute managed Python plus `-m hangeul_mcp.launcher`. A bare `hangeul-mcp` command is only valid when the installer also exposes a shim on PATH.

## Manual fallback

If you are managing the install yourself, use an absolute Python path and the module entrypoint:

```toml
[mcp_servers.hangeul-mcp]
command = "/absolute/path/to/python"
args = ["-m", "hangeul_mcp.server"]
```

If a managed install has already created a stable launcher shim on PATH, this shorter form is also valid:

```toml
[mcp_servers.hangeul-mcp]
command = "hangeul-mcp"
args = []
```

Project-local setup uses the same schema in `.codex/config.toml`.

PyPI publication is verified for `hangeul-mcp`. Install with `pip install --upgrade hangeul-mcp`, or use the reviewed managed installer with `-Version 0.4.0` when versioned update and rollback are required.
