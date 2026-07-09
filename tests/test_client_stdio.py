"""US-008: a real MCP client starts the stdio server and lists/calls tools.

This proves the documented stdio command works and that any standards-compliant
MCP client (Claude Desktop, Codex, Antigravity 2.0, ...) can discover the tools.
"""

import asyncio
import sys
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "sample_form.hwpx"


def test_stdio_server_lists_tools_and_calls():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def run():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "hangeul_mcp.server"]
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                names = {t.name for t in listed.tools}
                assert {
                    "detect_format",
                    "analyze_form",
                    "fill_form",
                    "extract_text",
                    "create_document_from_blocks",
                    "render_preview",
                    "extract_hwp_text",
                } <= names
                result = await session.call_tool("detect_format", {"path": str(FIXTURE)})
                assert result is not None and not result.isError

    asyncio.run(asyncio.wait_for(run(), timeout=40))
