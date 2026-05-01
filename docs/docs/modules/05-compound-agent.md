# Module 5 — Compound Agent

**Time**: 30 minutes

## What you'll build

One agent, four tools, deployed to Model Serving as `disa-cti-agent`.

| Tool | Backed by | When the agent picks it |
|---|---|---|
| `genie_query` | Module 3 Genie space | Quantitative / structured questions |
| `knowledge_assistant_search` | Module 4 KA endpoint | Doctrinal / definitional questions |
| `fetch_advisory_url` | Fetch MCP (allowlisted to CISA / NVD / MITRE) | User pasted a URL |
| `parse_pdf` | `ai_parse_document` over a UC volume path | User uploaded a PDF |

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

## Deployment

Logged with `mlflow.pyfunc.log_model`, registered to `disa_workshop.threat_intel.disa_cti_agent`, deployed via `databricks.agents.deploy()`. Scale-to-zero by default.

[Open the notebook →](https://github.com/your-handle/disa-genai-workshop/blob/main/notebooks/05_compound_agent.ipynb)
