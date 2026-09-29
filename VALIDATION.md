# Validation performed for this package

Checked on 2026-09-21 using Python 3.14 on macOS. The dependency versions installed for these checks are pinned in `requirements.txt`.

| Check | Result |
|---|---|
| `python -m pytest tests -q` | 10 passed |
| Date calculation, weekend boundaries, invalid range | Passed |
| Hour 1 two-tool graph | Executed; 12 available and 3 requested days |
| Raw API message protocol | Tested with a fake model client, including matching tool-call IDs; no paid API call |
| Chroma retrieval and carry-forward citation | Executed in demo mode; `LEAVE-02` returned |
| Seeded missing-sabbatical question | `not_in_policy`, exact refusal, empty citations |
| Conversation memory across service restart | Passed using SQLite checkpoints |
| Approval, rejection, pending-state protection, cross-employee resume | Passed |
| Idempotent mock write, overlapping leave, insufficient balance | Passed |
| API key separation and strict approval boolean | Passed |
| Leave-balance HTTP adapter | Server route and client adapter tested locally with a mocked HTTP transport |
| MCP discovery and invocation | Executed through a real separate stdio server process |
| CSV batch processing | Executed; output saved in `data/sample_answers.csv` |
| FastAPI HTTP smoke | Passed against a running Uvicorn server on localhost |
| HTTP approval flow | Submitted pending request and approved it successfully over HTTP |
| Source/config syntax | Parsed 25 Python files and deployment YAML |
| Sample output files | Generated from actual demo-mode runs; random IDs are examples |

Dependency deprecation warnings appeared in Starlette/AnyIO, Chroma, and LangSmith imports. They did not fail these tests.

## Checks requiring the learner's environment

- **Live model and API embeddings:** not executed. Supply your API key, switch to live mode, and run the hourly examples.
- **LangSmith tracing and hosted experiments:** integration code is present; no hosted trace or five-case experiment was created without credentials. The programmatic evaluator has local contract tests; the LLM judge needs a model key.
- **Docker build/run:** not executed because the Docker daemon was unavailable. Dockerfile and deployment YAML were inspected, but container execution is not claimed.
- **GitHub Actions, Cloud Run, and Hugging Face:** no deployment was run, no cloud URL was produced, and no green pipeline is claimed. Follow `hour_04/DEPLOYMENT.md` to configure and verify these in your accounts.
- **Windows/Linux:** not executed on those operating systems. Docker and CI target Linux/Python 3.14. The requirements exclude uvloop on Windows.

## Reproduce

From the project root after setup:

```bash
python -m pytest tests -q
python -m hour_03.mcp_agent
python -m hr_agent.batch
python -m uvicorn hour_04.api:app --host 127.0.0.1 --port 8080
```

Then, in another activated terminal:

```bash
export HR_BASE_URL=http://127.0.0.1:8080
export HR_EMPLOYEE_API_KEY=local-employee-key
python -m pytest hour_04/test_live.py -q
```

Use a fresh runtime for baseline numbers. Live evaluation expects the unchanged CSV fixtures and a clean balance of 12 days.
