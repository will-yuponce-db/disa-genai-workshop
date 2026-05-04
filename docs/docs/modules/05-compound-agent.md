# Module 5 — Compound Agent

**Time**: 30 minutes

## What you'll build

One agent, four tools, deployed to Model Serving as `disa-cti-agent`.

| Tool | Backed by | When the agent picks it |
|---|---|---|
| `genie_query` | Module 3 Genie space | Quantitative / structured questions |
| `knowledge_assistant_search` | Module 4 KA endpoint | Doctrinal / definitional questions |
| `fetch_advisory_url` | `requests.get` (allowlisted to CISA / NVD / MITRE domains) | User pasted a URL |
| `parse_pdf` | `ai_parse_document` over a UC volume path | User uploaded a PDF |

## Notebook flow

1. **Cell 2 (widgets)** reads `genie_space_id`, `ka_endpoint`, and `llm_endpoint` defaults from `_workshop_config`. Attendees never paste an id.
2. **Cell 4 (agent.py)** writes a self-contained agent module to `/tmp/disa_agent/agent.py`. It uses `mlflow.pyfunc.ResponsesAgent` and routes tool calls through `WorkspaceClient.api_client.do(...)` so it works under all auth modes (PAT, OAuth user, M2M).
3. **Cell 6 (smoke test)** instantiates the agent locally and asks it to list its tools without calling any.
4. **Cell 8 (log + register)** logs the model to `mlflow` and registers it to UC at `saf_aq_demo_catalog.disa_threat_intel.disa_cti_agent`.
5. **Cell 10 (deploy)** calls `databricks.agents.deploy(...)` to push the registered model version to a serving endpoint named `disa-cti-agent`.

The agent endpoint takes ~10-15 min to provision the first time. Re-deploys after that are minutes.

## Content-flattening fix

The `predict()` method must flatten `ResponseInputTextParam` content before forwarding to the LLM. Earlier versions concatenated structured content directly into the request body, which made `requests` fail with `Object of type ResponseInputTextParam is not JSON serializable`. The current `_flatten()` helper extracts `.text` from each content part and joins them with `\n`. Worth knowing if you customize the agent.

## End-to-end test

```
"Fetch https://www.cisa.gov/news-events/cybersecurity-advisories
 and tell me which CVEs are mentioned. Then check our asset inventory
 for any exposure, and tell me which STIG controls would mitigate."
```

The agent should:
1. Call `fetch_advisory_url` to pull the page.
2. Call `genie_query` to look up asset exposure.
3. Call `knowledge_assistant_search` to find matching STIGs.
4. Synthesize a single analyst-actionable answer with CVE / STIG / ATT&CK citations.

## What the notebook leaves to the UI

Nothing required. Optional things to look at after deploy:

- **Sidebar → Compute → Serving → disa-cti-agent** — watch the deployment status; click **Logs** to debug if the smoke test fails.
- **Mlflow tracing** — every call leaves a trace under the agent's experiment. Useful for showing tool-routing decisions to the audience.

[Open the notebook →](https://github.com/your-handle/disa-genai-workshop/blob/main/notebooks/05_compound_agent.ipynb)
