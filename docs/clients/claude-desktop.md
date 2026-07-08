# Claude Desktop

Edit `claude_desktop_config.json`:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "hangeul-mcp": {
      "command": "hangeul-mcp"
    }
  }
}
```

Module form (if the console script is not on PATH):

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

Restart Claude Desktop; the `hangeul-mcp` tools appear in the tools list.
