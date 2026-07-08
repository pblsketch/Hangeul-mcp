# Client setup (Claude Desktop · Codex · Antigravity 2.0)

Hangeul-mcp is a **standard stdio MCP server** that exposes **tools only** (no
client-specific features), so the same server works across every MCP client.

## Install

```bash
pip install git+https://github.com/pblsketch/Hangeul-mcp
# provides the console command:  hangeul-mcp
```

Run command (either works):

- `hangeul-mcp`  (console entrypoint, after install)
- `python -m hangeul_mcp.server`  (module form)

## Tools exposed

- `detect_format(path)`
- `analyze_form(path)` — form understanding (fields + kinds + addresses)
- `fill_form(path, values, out_path, ...)` — format-preserving fill
- `extract_text(path)`

> COM live-apply tools (v2) are added later and only activate on Windows with
> Hangul (한글) installed; elsewhere they degrade gracefully.

See the per-client snippets:
- [claude-desktop.md](claude-desktop.md)
- [codex.md](codex.md)
- [antigravity.md](antigravity.md)
