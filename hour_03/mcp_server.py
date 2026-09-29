"""Prebuilt workshop server: read-only synthetic calendar via MCP stdio."""
import os
from mcp.server.fastmcp import FastMCP
from hr_agent.business import calendar

server = FastMCP('workshop-calendar')

@server.tool()
def mock_calendar() -> dict:
    """Read the calendar of the employee identity bound when this process starts."""
    return calendar(os.environ.get('HR_EMPLOYEE','E001'))

if __name__ == '__main__':
    server.run(transport='stdio')
