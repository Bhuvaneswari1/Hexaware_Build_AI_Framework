import asyncio
import json
import os
import sys
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage
from hr_agent.agent import build_agent, observations
from hr_agent.tools import tools_for
from hr_agent.answers import render
from hr_agent.config import ROOT

async def run():
    # A separate child process owns the MCP tool; stdio carries JSON-RPC messages.
    client = MultiServerMCPClient({'calendar':{'transport':'stdio','command':sys.executable,
        'args':['-m','hour_03.mcp_server'],'cwd':str(ROOT),
        'env':{**os.environ,'HR_EMPLOYEE':'E001'}}})
    external = await client.get_tools()
    external_tool = next(t for t in external if t.name=='mock_calendar')
    # The workshop graph is synchronous. Run its external coroutine in its worker thread.
    def call_calendar():
        return asyncio.run(external_tool.ainvoke({}))
    adapter = StructuredTool.from_function(call_calendar, name='mock_calendar',
                                         description=external_tool.description)
    local = [t for t in tools_for('E001',3) if t.name != 'mock_calendar']
    graph = build_agent(local+[adapter])
    result = await asyncio.to_thread(graph.invoke, {'messages':[HumanMessage(content='Show my calendar and leave balance')]}, {'recursion_limit':16})
    print(json.dumps({'external_tools':[t.name for t in external],
                      'observations':observations(result['messages'])},indent=2))

if __name__ == '__main__':
    asyncio.run(run())
