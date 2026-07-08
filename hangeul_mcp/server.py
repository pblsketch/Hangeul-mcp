"""Hangeul-mcp MCP server entrypoint.

Scaffold only. The real MCP tool wiring (detect_format, analyze_form,
fill_form, extract_text) lands in US-007 on top of the FastMCP stdio server.
"""

from __future__ import annotations


def main() -> None:
    """Console entrypoint for the ``hangeul-mcp`` command.

    The scaffold intentionally does not start a server yet; it exists so
    packaging and the console-script entrypoint can be verified (US-001).
    """
    raise SystemExit(
        "hangeul-mcp: server not implemented yet (US-007). "
        "This scaffold verifies packaging and the console entrypoint only."
    )


if __name__ == "__main__":
    main()
