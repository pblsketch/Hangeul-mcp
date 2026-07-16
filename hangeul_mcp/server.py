from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from hangeul_mcp.tools_assessment import register_assessment_tools
from hangeul_mcp.tools_core import register_core_tools
from hangeul_mcp.tools_delegate import register_delegate_tools
from hangeul_mcp.tools_file_edit import register_file_edit_tools

from hangeul_mcp.tools_live import register_live_tools
from hangeul_mcp.tools_live_table import register_live_table_tools
from hangeul_mcp.tools_read import register_read_tools


mcp = FastMCP("hangeul-mcp")

for register in (
    register_core_tools,
    register_assessment_tools,
    register_read_tools,
    register_file_edit_tools,
    register_delegate_tools,
    register_live_tools,
    register_live_table_tools,
):
    globals().update(register(mcp))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
