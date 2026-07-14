# Claude Desktop

Verified against current official Claude MCP/Desktop docs on **2026-07-12**.

- Official sources:
  - https://docs.anthropic.com/en/docs/mcp
  - https://modelcontextprotocol.io/docs/develop/connect-local-servers
- Confidence: **high**
- Exact schema verified: **JSON `mcpServers`**
- Official paths verified:
  - `~/Library/Application Support/Claude/claude_desktop_config.json`
  - `%APPDATA%\Claude\claude_desktop_config.json`

## Recommended setup

```bash
hangeul-mcp-manage setup --client claude
hangeul-mcp-manage doctor
```

This repository only auto-manages the two official paths above. It does **not** invent a Linux Claude Desktop config path.

Managed installs currently register a stable launcher command as an absolute managed Python plus `-m hangeul_mcp.launcher`. A bare `hangeul-mcp` command is only valid when the installer also exposes a shim on PATH.

## Manual fallback

If you are not using a managed install, configure Claude Desktop with an absolute Python path and the module entrypoint:

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
      "command": "hangeul-mcp"
    }
  }
}
```

Restart Claude Desktop after editing the config.

PyPI publication is verified for `hangeul-mcp`. Install with `pip install --upgrade hangeul-mcp`, or use the reviewed managed installer with `-Version 0.5.1` when versioned update and rollback are required.
