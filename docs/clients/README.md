# Client setup (Claude Desktop · Codex · Antigravity)

Hangeul-mcp is a standard stdio MCP server. The server stays the same; the safe setup path depends on each client's officially documented MCP surface.

## Recommended install path

1. Download the reviewed installer script, inspect it locally, then run it.
2. Run `hangeul-mcp-manage setup --client <name>`.
3. Run `hangeul-mcp-manage doctor`.
4. If setup returns a manual-only or scope-selection result, apply the generated snippet using the official client surface below instead of guessing.

```bash
hangeul-mcp-manage setup --client claude
hangeul-mcp-manage setup --client codex
hangeul-mcp-manage setup --client antigravity
hangeul-mcp-manage doctor
```

Managed installs should register a stable launcher command, typically the managed base Python plus `-m hangeul_mcp.launcher`. The bare `hangeul-mcp` command is only a convenience shim when the installer exposes it on PATH. Unmanaged installs should use an absolute Python path plus `-m hangeul_mcp.server`.

## Automation scope in this repository

- **Claude Desktop** — auto-manages only the official macOS and Windows `claude_desktop_config.json` paths.
- **Codex** — auto-manages only the global `~/.codex/config.toml`. If project-local `.codex/config.toml` already exists, setup fails closed and returns manual scope guidance.
- **Antigravity** — auto-manages the official global `~/.gemini/config/mcp_config.json` when no workspace-local `.agents/mcp_config.json` exists. If a workspace config already exists, setup fails closed and returns manual scope guidance instead of guessing scope.

## Officially verified sources

Access date: **2026-07-12**

| Client | Supported surface verified | Official source URL | Exact command/config schema verified | Confidence |
| --- | --- | --- | --- | --- |
| Claude Desktop | Claude Desktop local MCP config on macOS/Windows | https://docs.anthropic.com/en/docs/mcp ; https://modelcontextprotocol.io/docs/develop/connect-local-servers | JSON `mcpServers`; `~/Library/Application Support/Claude/claude_desktop_config.json`; `%APPDATA%\\Claude\\claude_desktop_config.json`; restart after edit | high |
| Codex | Codex CLI / ChatGPT desktop / IDE shared Codex host | https://developers.openai.com/codex/mcp/ ; https://learn.chatgpt.com/docs/extend/mcp?surface=cli ; https://learn.chatgpt.com/docs/config-file/config-reference | TOML `[mcp_servers.hangeul-mcp]`; `~/.codex/config.toml`; `.codex/config.toml`; `codex mcp list/get/add/remove` | high |
| Antigravity | Antigravity 2.0 / IDE / CLI shared MCP config | https://antigravity.google/docs/mcp ; https://codelabs.developers.google.com/google-workspace-mcp-antigravity | JSON `mcpServers` with `command`/`args` for stdio and `serverUrl` for remote; `~/.gemini/config/mcp_config.json`; `.agents/mcp_config.json`; UI Settings/Customizations and CLI `/mcp` manager | medium-high |

## Client-specific docs

- [claude-desktop.md](claude-desktop.md)
- [codex.md](codex.md)
- [antigravity.md](antigravity.md)

## Supported surface reminder

- Standard stdio MCP tools server: supported.
- Windows live/open-document flows: still more conservative than file mode.
- Headless `.hwp` reading: still unsupported and reported honestly as unavailable.
