# Codex

Codex reads MCP servers from `~/.codex/config.toml`:

```toml
[mcp_servers.hangeul-mcp]
command = "hangeul-mcp"
args = []
```

Module form:

```toml
[mcp_servers.hangeul-mcp]
command = "python"
args = ["-m", "hangeul_mcp.server"]
```

Because the server speaks standard MCP over stdio and exposes only tools, Codex
lists and calls `analyze_form` / `fill_form` with no extra adapters.
