# Module 0 — Setup

**Time**: 10 minutes (instructor runs once on Vocareum; attendees just sign in)

## Attendee setup

1. Open the Vocareum lab page from the email you received.
2. Click **Start Lab**. Vocareum provisions your Databricks workspace user and lands you in the workspace.
3. Open `notebooks/00_setup` from the workspace file browser. Click **Run all**.

That's it. The notebook does the rest.

## What `00_setup` does

| Step | Output |
|---|---|
| Catalog + schema + volumes | `main.cti_<user>`, plus `raw_advisories`, `raw_stigs`, `ka_corpus` volumes |
| CISA KEV catalog | `kev_catalog` table (~1,587 rows) |
| NVD 2.0 REST API pull | `cves` table (~32k CVEs from the last 6 months) |
| MITRE ATT&CK STIX bundle | `attack_techniques` (~858) and `attack_groups` (~189) |
| Synthetic DoD assets | `affected_assets` (500 rows) |
| CISA advisory PDFs | uploaded to `raw_advisories` volume; falls back to 5 synthetic PDFs if egress to cisa.gov is blocked |
| DoD STIG XCCDF zips | parsed to per-rule text snippets in `raw_stigs`; falls back to 4 hand-written excerpts if egress to dl.dod.cyber.mil is blocked |
| `_workshop_config` table | seeded with `catalog`, `schema`, `llm_endpoint` defaults — read by every downstream notebook |

The notebook is idempotent. Re-running it overwrites the data tables and is safe.

## Catalog and schema choice

The notebooks default to `main.cti_<user>`. If you do not have `CREATE SCHEMA` on that catalog, change the catalog name in `00_setup` (and the same string appears in 01–06; a global find-and-replace works) before running.

## One-time UI prerequisites

These are workspace settings, not anything an attendee touches mid-workshop. Set them once before running 00_setup:

| Setting | Where | Why |
|---|---|---|
| Agent Bricks | Workspace settings → Previews → **Agent Bricks** | Module 4 creates the Knowledge Assistant via the Agent Bricks API; the workspace toggle gates it. |
| Genie | Workspace settings → Previews → **AI/BI Genie** | Default-on in newer workspaces. |
| Mosaic AI Model Serving | Workspace settings → Compute → Serving | Default-on. |
| Vector Search | Workspace settings → Compute → Vector Search | Default-on. |
| Foundation model endpoints | Compute → Serving | Confirm `databricks-claude-haiku-4-5`, `databricks-claude-sonnet-4-6`, and `databricks-gte-large-en` are reachable. |
| Serverless SQL warehouse | SQL → Warehouses | Required for Genie + the app. |

[Open the notebook on GitHub →](https://github.com/will-yuponce-db/disa-genai-workshop/blob/main/notebooks/00_setup.ipynb)
