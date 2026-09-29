# Hour 3 — Multi-agent workflow, four tools, approval, MCP, LangSmith

**Use case:** Asha requests leave and wants HR context before her manager approves it. The assistant must combine policy, leave balance, payroll, and calendar facts. Only a manager decision may trigger the mock write.

## 60-minute run sheet

| Time | Topic | Hands-on result |
|---|---|---|
| 00–12 | ReAct vs plan-and-execute; routing; approval; MCP; traces | Explain the supervisor and trust boundaries |
| 12–38 | Four tools and approval gate | Multi-specialist response, then pause/resume with durable local state |
| 38–60 | External MCP tool and LangSmith | Replace a local calendar read with MCP; inspect a complete trace |

## Multi-agent roles and handoffs

| Component | Responsibility | Tools or state |
|---|---|---|
| Supervisor | Produce a bounded list of required specialists | Typed `Plan.roles` |
| Policy agent | Find policy evidence relevant to the request | `policy_search` only |
| Records agent | Fetch employee-specific records | `leave_balance`, `payroll_lookup`, `mock_calendar` |
| Synthesis node | Combine evidence into one structured response | Validated `Answer` |
| Approval node | Pause and expose the exact proposed action | `interrupt()` plus SQLite checkpoint |
| Write node | Apply approved leave once | Transactional ledger; balance and calendar derive from it |

The supervisor returns an explicit plan. Each specialist uses the model/tool/observation loop from Hour 1. Specialists run sequentially, passing evidence through workflow state. A policy-only question can skip the records agent. The synthesis and write nodes are workflow steps, not additional autonomous agents.

This combines plan-and-execute at the outer level with an action/observation loop inside each specialist. The TOC's four tools are **read tools**; `apply_leave` is a separate controlled action. Date counting remains a deterministic helper for request validation.

## Lab A — Query four tools

1. Start from the root setup. Use demo mode for reproducible output, then repeat in live mode.
2. Run:

   ```bash
   python -m hour_03.app "Explain the leave policy and show my leave balance, payroll and calendar"
   ```

3. Inspect `evidence`: policy passages, 12 available days on a fresh runtime, INR 82000 scheduled net pay, and no initial calendar events. `sample_read_output.json` contains the full sample.
4. Open `workflow.py`. Follow `supervisor → policy_agent → records_agent → synthesis`. Explain why the model cannot call `apply_leave` from either specialist.

### Exercise the leave-balance HTTP API

The default adapter reads the CSV/ledger directly so the workshop starts with one command. To exercise the TOC's API boundary:

1. In terminal A, from the project root:

   ```bash
   export HR_RECORDS_API_KEY=local-records-key
   python -m uvicorn hour_03.records_api:app --host 127.0.0.1 --port 8090
   ```

2. In terminal B, activate the same environment and run:

   ```bash
   export HR_RECORDS_API_KEY=local-records-key
   export HR_RECORDS_API_URL=http://127.0.0.1:8090
   python -m hour_03.app "What is my leave balance?"
   ```

3. Confirm `GET /leave-balance` appears in terminal A. The tool now crosses HTTP and checks the returned identity. This small API binds to `E001`; do not use it for other CLI employee identities.
4. After the exercise: `unset HR_RECORDS_API_URL HR_RECORDS_API_KEY` in terminal B, and stop terminal A with Ctrl+C. These settings are optional and are not needed for the final cloud service.

## Lab B — Request leave, pause, then approve

1. Use a fresh runtime if you need the baseline 12-day balance.
2. Submit a structured date range:

   ```bash
   python -m hour_03.app "Apply leave and explain the leave policy" --thread h3-leave --start 2026-10-05 --end 2026-10-07
   ```

   Expected excerpt:

   ```json
   {
     "thread_id":"h3-leave",
     "status":"pending_approval",
     "answer":"3 working days requested. Waiting for manager approval.",
     "approval":{
       "employee_id":"E001",
       "leave":{"start":"2026-10-05","end":"2026-10-07"},
       "working_days":3,
       "action":"Apply mock leave and update calendar"
     }
   }
   ```

   `request_id` is generated and is shown in the full sample. Dates are provided in structured fields; free text alone never causes a leave write.

3. Run a balance query in another thread. It must still show 12. No calendar event exists yet.
4. Resume as the trusted CLI instructor acting as manager:

   ```bash
   python -m hour_03.app --thread h3-leave --resume approve
   ```

   Expected: `status: applied`, `answer: Applied 3 working days to the mock calendar.`

5. Check the changed data:

   ```bash
   python -m hour_03.app "Show my leave balance and calendar"
   ```

   Expect 9 available days and one calendar event. `sample_pending_output.json`, `sample_approved_output.json`, and `sample_after_output.json` show the executed sequence.

6. Try rejection with another range:

   ```bash
   python -m hour_03.app "Apply leave" --thread h3-reject --start 2026-11-02 --end 2026-11-03
   python -m hour_03.app --thread h3-reject --resume reject
   ```

   Expect `rejected`; no deduction and no event for that request.

7. Try resuming `h3-leave` again. It must fail because no pending approval remains. Try `--employee E003` on a new request; the zero balance must reject it before an interrupt.

The interrupted node starts again on resume, so the approval node performs no writes before `interrupt()`. The actual write is separate and idempotent. Local checkpoints and the leave ledger survive CLI restart when `.runtime` remains. This follows the [LangGraph interrupt contract](https://docs.langchain.com/oss/python/langgraph/interrupts).

## Lab C — Attach the supplied MCP server

1. Open `hour_03/mcp_server.py`: it is a prebuilt workshop MCP server exposing one read-only calendar tool.
2. Run:

   ```bash
   python -m hour_03.mcp_agent
   ```

3. The adapter launches a separate Python process over stdio, discovers `mock_calendar`, replaces the local tool, and runs a question through the agent. Expected top-level output includes:

   ```json
   {"external_tools":["mock_calendar"],"observations":[...]}
   ```

   See `sample_mcp_output.json`. MCP returns content blocks, which remain visible in this protocol-focused sample. The four-tool core application uses the local calendar adapter by default; this dedicated lab demonstrates the external replacement explicitly.
4. Follow server discovery → tool schema → agent tool call → JSON-RPC request → result. A stdio server must keep diagnostic logging off protocol stdout. MCP is a tool connection protocol; it is not the multi-agent supervisor.

The client setup uses [LangChain MCP adapters](https://docs.langchain.com/oss/python/langchain/mcp).

## Lab D — Inspect LangSmith

1. Set the following in `.env` and start a new process:

   ```dotenv
   HR_MODE=live
   LANGSMITH_TRACING=true
   LANGSMITH_API_KEY=your-key
   LANGSMITH_PROJECT=hr-agent-workshop
   ```

2. Run the four-tool query, then a new leave request and its approval.
3. In LangSmith, open project `hr-agent-workshop` and the `hr-request` trace. Follow supervisor → specialist → model/tool → synthesis → interrupt. Open the separate `hr-manager-resume` trace to inspect the resumed write. A pause and later resume are separate invocations tied to the checkpoint thread.
4. Record the tools called, policy IDs, latency, and token usage. The demo fixture has no model tokens. Check that there is no write before the interrupt.
5. Run the MCP lab with tracing enabled. Find its graph/tool spans and compare the external tool result with the local one.

## Artifact check

Show one four-tool response, one pending request, an approved or rejected result, and the corresponding trace in your account. Trace screenshots/URLs are account-specific and are not fabricated in this package. Hour 4 exposes this same workflow through authenticated API routes and adds deployment verification.
