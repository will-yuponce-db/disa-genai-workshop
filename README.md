# DISA GenAI Workshop

A 2.5 hour, hands-on Databricks workshop for cyber threat intelligence and vulnerability management on the Mosaic AI stack.

> Audience: DISA analysts and engineers (mixed). Hosted on Vocareum. All data is unclassified and public open source.

## What you will build

A compound AI agent for **cyber threat intelligence**. By the end of the workshop, you can ask a single natural-language question — *"A new CISA advisory just dropped at this URL. Find related KEV entries, tell me which STIG controls apply, and summarize the operational impact"* — and the agent will fetch the advisory, parse it, query CVE/KEV/STIG tables, ground its answer in DoD documentation, and respond in seconds.

The workshop closes with a **live vibe-code demo**: paste a Genie-generated SQL query into Claude using a templated prompt and watch a working React chart appear in the deployed Databricks App.

## Story

```
A new CISA advisory drops.
  -> Parse the PDF (ai_parse_document)
  -> Match CVEs against the KEV catalog (Genie)
  -> Find the STIG controls that mitigate the threat (Knowledge Assistant)
  -> Pull live updates from cisa.gov (Fetch MCP)
  -> Compound agent ties it all together
  -> Embedded in a Databricks App you can extend with vibe-coded components
```

## Modules

| # | Module | Time | Notebook / Asset |
|---|---|---|---|
| 0 | Vocareum sign-in + workspace tour | 10m | live |
| 1 | Document ingest with AI Functions | 30m | `notebooks/01_ingest_advisories.ipynb` |
| 2 | AI Playground walkthrough | 15m | live |
| 3 | Genie space over CVE / KEV / STIG | 25m | `notebooks/03_genie_setup.ipynb` |
| 4 | Knowledge Assistant (Agent Bricks) | 20m | `notebooks/04_knowledge_assistant.ipynb` |
| 5 | Compound agent + Fetch MCP | 30m | `notebooks/05_compound_agent.ipynb` |
| 6 | App embed + live vibe-code | 25m | `app/` + `prompts/vibe_code_component.md` |

## Public datasets

| Dataset | Source | Used in |
|---|---|---|
| CISA KEV catalog | [cisa.gov/known-exploited-vulnerabilities-catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) | Modules 3, 5 |
| NIST NVD | NVD JSON API | Module 3 |
| MITRE ATT&CK | STIX 2.1 JSON | Module 4 |
| CISA advisories | cisa.gov/news-events (PDF) | Modules 1, 4 |
| DoD STIGs | [public.cyber.mil](https://public.cyber.mil) (XCCDF) | Module 4 |

## Repo layout

```
disa-genai-workshop/
  notebooks/         # 5 hands-on notebooks
  data/              # Sample advisory PDFs + STIGs + seed SQL
  app/               # Databricks App fork — chatbot UI wired to compound agent
  prompts/           # Take-home vibe-code prompt
  vocareum/          # Lifecycle scripts for the Vocareum lab platform
  docs/              # MkDocs Material site (auto-deployed to GH Pages)
```

## Prerequisites

- A Databricks workspace with **Mosaic AI**, **Agent Bricks**, **Genie**, **Vector Search**, and **AI Functions** enabled
- A serverless SQL warehouse
- `databricks-cli` configured with a profile (default `e2-demo-west`)
- Python 3.11+ for local notebook authoring

For Vocareum-hosted runs, none of the above is needed by attendees — see [SETUP.md](SETUP.md).

## Quick start (instructor / dry-run)

```bash
# 1. Provision the workspace
databricks bundle deploy -t dev

# 2. Run the setup notebook
databricks bundle run setup_disa_workshop -t dev

# 3. Walk the modules
# Open notebooks/01_ingest_advisories.ipynb in the workspace and run top-to-bottom.

# 4. Deploy the app
cd app && npm install && npm run build
databricks apps deploy disa-cti --source-code-path /Workspace/Users/${USER}@databricks.com/disa-genai-workshop/app
```

## Docs site

Live docs: `https://<your-handle>.github.io/disa-genai-workshop/`

Build locally:

```bash
cd docs
pip install mkdocs-material
mkdocs serve  # http://127.0.0.1:8000
```

## License

Apache 2.0. See [LICENSE](LICENSE).
