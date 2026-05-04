# DISA GenAI Workshop

A 2.5 hour, hands-on Databricks workshop for cyber threat intelligence and vulnerability management on the Mosaic AI stack.

> Audience: DISA analysts and engineers (mixed). Hosted on Vocareum. All data is unclassified and public open source.

📖 **Live docs:** <https://will-yuponce-db.github.io/disa-genai-workshop/>

## What you will build

A compound AI agent for **cyber threat intelligence**. By the end of the workshop, you can ask a single natural-language question — *"A new CISA advisory just dropped at this URL. Find related KEV entries, tell me which STIG controls apply, and summarize the operational impact"* — and the agent will fetch the advisory, parse it, query CVE/KEV/STIG tables, ground its answer in DoD documentation, and respond in seconds.

The workshop closes with a stock Databricks Apps template (Streamlit chat works) wired up to the agent endpoint. The instructor can extend it ad-hoc by asking Genie a question and pasting the resulting SQL into Claude.

## Story

```
A new CISA advisory drops.
  -> Parse the PDF (ai_parse_document)
  -> Match CVEs against the KEV catalog (Genie)
  -> Find the STIG controls that mitigate the threat (Knowledge Assistant)
  -> Pull live updates from cisa.gov (Fetch / requests)
  -> Compound agent ties it all together
  -> Wired into a stock Databricks Apps template (Streamlit chat)
```

## Modules

Every module is a runnable notebook. Each one writes its outputs (Genie space id, KA endpoint, warehouse id, etc.) into a shared Delta table — `main.cti_<user>._workshop_config` — that downstream notebooks read on startup. Attendees never copy an id from one notebook to another, and never have to leave the notebook for the Databricks UI mid-workshop.

| # | Module | Time | Notebook |
|---|---|---|---|
| 0 | Workspace bootstrap | 10m | `notebooks/00_setup.ipynb` |
| 1 | Document ingest with AI Functions | 30m | `notebooks/01_ingest_advisories.ipynb` |
| 2 | Foundation models (programmatic Playground) | 15m | `notebooks/02_ai_playground.ipynb` |
| 3 | Genie space over CVE / KEV / STIG | 25m | `notebooks/03_genie_setup.ipynb` |
| 4 | Knowledge Assistant (Agent Bricks) | 20m | `notebooks/04_knowledge_assistant.ipynb` |
| 5 | Compound agent | 30m | `notebooks/05_compound_agent.ipynb` |
| 6 | NetOps log analysis with `ai_query` (bulk inference over real outage reports) | 20m | `notebooks/06_netops_ai_query.ipynb` |
| 7 | App embed (stock Apps template) | 25m | `notebooks/07_deploy_app.ipynb` |

## Public datasets

Validated against live sources during the May 2026 instructor dry-run on `fevm-saf-aq-demo`:

| Dataset | Source | Status from a Databricks workspace |
|---|---|---|
| CISA KEV catalog | `cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` | Reachable, ~1,587 entries |
| NIST NVD CVEs | NVD 2.0 REST API (`services.nvd.nist.gov/rest/json/cves/2.0`) | Reachable, ~32k CVEs over a 6-month window |
| MITRE ATT&CK | `raw.githubusercontent.com/mitre/cti` | Reachable, ~858 techniques + 189 groups |
| CISA advisory PDFs | `cisa.gov/news-events/...` | **Often blocked by workspace WAF**; falls back to synthetic generated PDFs |
| DoD STIG XCCDF ZIPs | `dl.dod.cyber.mil/wp-content/uploads/stigs/zip/` | Reachable, parsed into per-rule text snippets; falls back to 4 hand-written excerpts |

The legacy NVD JSON 1.1 feeds (`nvd.nist.gov/feeds/json/cve/1.1/...`) are deprecated and return 403; use the 2.0 REST API.

## Repo layout

```
disa-genai-workshop/
  notebooks/         # 8 hands-on notebooks (00-07, plus the optional 01b DLT path)
  data/              # seed SQL fixtures (advisories/STIGs/etc. are downloaded by 00_setup)
  vocareum/          # lifecycle scripts for the Vocareum lab platform
  docs/              # MkDocs Material site (auto-deployed to GH Pages)
```

## Prerequisites

- A Databricks workspace with **Mosaic AI**, **Agent Bricks**, **Genie**, **Vector Search**, and **AI Functions** enabled
- A serverless SQL warehouse
- A Unity Catalog catalog you have `CREATE SCHEMA` on (default: `main`; see `SETUP.md` to change)
- `databricks` CLI configured with a profile

For Vocareum-hosted runs, none of the above is needed by attendees — see [SETUP.md](SETUP.md).

The list of one-time UI clicks (Agent Bricks workspace toggle, etc.) is in [SETUP.md](SETUP.md) and the docs site.

## Quick start (instructor / dry-run)

```bash
# 1. Import notebooks into your workspace
databricks workspace import-dir notebooks /Workspace/Users/${USER}@databricks.com/disa-genai-workshop/notebooks --overwrite --profile <your-profile>

# 2. Run notebooks in order via the workspace UI, or as one-off serverless jobs:
for nb in 00_setup 01_ingest_advisories 02_ai_playground 03_genie_setup 04_knowledge_assistant 05_compound_agent 06_netops_ai_query 07_deploy_app; do
  cat > /tmp/run_${nb}.json <<EOF
  {"run_name":"disa_${nb}","tasks":[{"task_key":"r","notebook_task":{"notebook_path":"/Workspace/Users/${USER}@databricks.com/disa-genai-workshop/notebooks/${nb}"}}]}
EOF
  databricks jobs submit --json @/tmp/run_${nb}.json --profile <your-profile>
done
```

Each notebook reads upstream artifacts from `_workshop_config`, so you can run them in any order as long as 00 has run first; 03 and 04 must run before 05; 06 (NetOps) is independent and can run any time after 00; 07 (app) needs 05 deployed.

## Fallback: download all notebooks as a zip

If the Vocareum auto-import fails (or you want a local copy), grab the latest bundle directly from this repo:

```
https://github.com/will-yuponce-db/disa-genai-workshop/raw/main/dist/disa-genai-workshop-notebooks.zip
```

Then `databricks workspace import-dir` it into your own workspace, or unzip and `Run All` from the UI. The zip is rebuilt automatically by `.github/workflows/build-zip.yml` whenever any notebook changes on `main`.

## Catalog and schema

The notebooks default to writing into `main.cti_<user>`. If you don't have CREATE rights on that catalog, change the catalog name in 00 (and the same string appears in 01-06; a global find-and-replace works) before running. Each attendee gets their own schema `cti_<sanitized-username>` (derived in `_config.ipynb`).

You'll also need `CREATE SCHEMA`, `CREATE TABLE`, `CREATE VOLUME`, and `CREATE FUNCTION` on the catalog you choose.

## Docs site

Live docs: <https://will-yuponce-db.github.io/disa-genai-workshop/>

Build locally:

```bash
cd docs
pip install -r requirements.txt
mkdocs serve  # http://127.0.0.1:8000
```

## License

Apache 2.0. See [LICENSE](LICENSE).
