# Antigravity 2.0

Antigravity 2.0 uses the common `mcpServers` JSON format (add via its MCP
settings / config file):

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

Module form:

```json
{
  "mcpServers": {
    "hangeul-mcp": {
      "command": "python",
      "args": ["-m", "hangeul_mcp.server"]
    }
  }
}
```

The server is a plain stdio MCP tools server, so Antigravity discovers the
`hangeul-mcp` tools through the standard MCP handshake — no client-specific code.
