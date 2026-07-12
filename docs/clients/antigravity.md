# Antigravity

Verified against current official Antigravity MCP docs on **2026-07-12**.

- Official sources:
  - https://antigravity.google/docs/mcp
  - https://codelabs.developers.google.com/google-workspace-mcp-antigravity
- Confidence: **medium-high**
- Exact schema verified: **JSON `mcpServers` with `command`/`args` for stdio and `serverUrl` for remote**
- Official config surfaces verified:
  - Shared global config: `~/.gemini/config/mcp_config.json`
  - Workspace-local config: `.agents/mcp_config.json`
- Official management surfaces verified:
  - Antigravity 2.0: **Settings → Customizations → Installed MCP Servers**
  - Antigravity CLI: `/mcp`

## Recommended setup

```bash
hangeul-mcp-manage setup --client antigravity
hangeul-mcp-manage doctor
```

This repository auto-manages the official global `~/.gemini/config/mcp_config.json` when no workspace-local `.agents/mcp_config.json` exists. If workspace-local config already exists, setup fails closed and returns manual scope guidance instead of choosing between global and workspace configuration for you.

For managed installs, the generated config currently points at a stable launcher command in the form of an absolute managed Python plus `-m hangeul_mcp.launcher`. A bare `hangeul-mcp` command is only valid when the installer also exposes a shim on PATH.

## Manual stdio snippet

If you are not using a managed install, configure Antigravity with an absolute Python path and the module entrypoint:

```json
{
  "mcpServers": {
    "hangeul-mcp": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "hangeul_mcp.server"]
    }
  }
}
```

If a managed install already provides a stable launcher shim on PATH, this shorter form is also valid:

```json
{
  "mcpServers": {
    "hangeul-mcp": {
      "command": "hangeul-mcp",
      "args": []
    }
  }
}
```

## Remote note

Official Antigravity remote MCP examples use `serverUrl`, not `url`. This repository's local Hangeul-mcp helper currently configures only the verified **stdio** shape above; it does not auto-generate remote `serverUrl` entries.

PyPI publication is not yet verified, so prefer the managed installer flow or a source install over PyPI-only instructions.
