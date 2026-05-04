# Setup Guide (Instructor / Vocareum Admin)

This guide walks an instructor or Vocareum admin through provisioning a workspace for the DISA GenAI workshop. The procedure was validated end-to-end on `fevm-saf-aq-demo` in May 2026.

The workshop is fully programmatic. Attendees never have to leave a notebook to click through the Databricks UI mid-workshop. Resources are namespaced per attendee — every attendee gets their own schema, Genie space, Knowledge Assistant, agent endpoint, and Databricks App. The **only resource shared across attendees is the catalog**.

## 1. One-time UI prerequisites (workspace admin)

Set these once per workspace before the workshop. Without them, the notebooks cannot create the resources they depend on.

| Toggle | Where | Why |
|---|---|---|
| **Agent Bricks** | Workspace settings → Previews → Agent Bricks | Module 4 creates a Knowledge Assistant via the Agent Bricks REST API; the workspace toggle gates the API. |
| **AI/BI Genie** | Workspace settings → Previews → AI/BI Genie | Module 3 creates a Genie space via REST. Default-on in newer workspaces. |
| **Mosaic AI Model Serving** | Workspace settings → Compute → Serving | Module 5 deploys the compound agent. Default-on. |
| **Vector Search** | Workspace settings → Compute → Vector Search | Default-on. |
| **Unity Catalog** | `SHOW CATALOGS` shows `system` and a workspace catalog | Required. |
| **Foundation model endpoints** | `SELECT ai_query('databricks-claude-haiku-4-5', 'hi')` runs | The notebooks default to: `databricks-claude-haiku-4-5`, `databricks-claude-sonnet-4-6`, `databricks-gte-large-en`. |
| **Serverless SQL warehouse** | `databricks warehouses list` shows at least one | The notebooks pick the first serverless warehouse automatically. |

## 2. Pick the shared catalog (one-time)

Every attendee writes into one shared catalog. Default: `main`. To change it, edit the single `CATALOG = "..."` line in [`notebooks/_config.ipynb`](notebooks/_config.ipynb).

The catalog must allow `account users` (or whichever group attendees belong to) to:

- `USE CATALOG`
- `CREATE SCHEMA`
- `CREATE TABLE`, `CREATE VOLUME`, `CREATE FUNCTION`
- `SELECT`, `READ VOLUME`

```sql
GRANT USE_CATALOG, CREATE_SCHEMA ON CATALOG main TO `account users`;
```

Each attendee's per-user schema is named `cti_<sanitized-username>` (derived in `_config.ipynb`), so two attendees with usernames `alice@…` and `bob@…` get `cti_alice` and `cti_bob` schemas inside the same catalog.

## 3. Run the notebooks in order

```bash
databricks workspace import-dir notebooks \
  /Workspace/Users/${USER}@databricks.com/disa-genai-workshop/notebooks \
  --overwrite --profile <your-profile>
```

Then submit each as a one-off job (or open in the workspace UI and click Run All):

```bash
for nb in 00_setup 01_ingest_advisories 02_ai_playground 03_genie_setup 04_knowledge_assistant 05_compound_agent 06_deploy_app; do
  cat > /tmp/run_${nb}.json <<EOF
{"run_name":"disa_${nb}","tasks":[{"task_key":"r","notebook_task":{"notebook_path":"/Workspace/Users/${USER}@databricks.com/disa-genai-workshop/notebooks/${nb}"}}]}
EOF
  databricks jobs submit --json @/tmp/run_${nb}.json --profile <your-profile>
done
```

| Notebook | What it does | Time |
|---|---|---|
| `_config` | Defines `CATALOG` (shared) and per-user names. Imported by every other notebook via `%run ./_config`. | n/a |
| `00_setup` | Per-user schema + volumes; pulls KEV / NVD / ATT&CK / synthetic assets / STIGs; seeds `<schema>._workshop_config` | ~5 min |
| `01_ingest_advisories` | `ai_parse_document` + `ai_query` over CISA advisory PDFs | ~3 min |
| `02_ai_playground` | Foundation model side-by-side and tool-call probes | ~1 min |
| `03_genie_setup` | Creates per-user Genie space `DISA Threat Intel (<user>)` via REST | ~1 min |
| `04_knowledge_assistant` | Creates per-user KA `disa-cti-knowledge-<user>` via REST; KA endpoint warms up async (~10-20 min) | ~1 min |
| `05_compound_agent` | Logs + registers + deploys per-user agent endpoint `disa-cti-agent-<user>` | ~3 min log/register, ~10-15 min endpoint provision |
| `06_deploy_app` | Patches `app.yaml`, syncs source to workspace, creates+deploys per-user App `disa-cti-<user>` | ~5-10 min |

The notebooks are idempotent. Re-running 03/04 reuses an existing space/KA by display name. Re-running 05 logs a new model version and updates the endpoint. Re-running 06 deploys a new revision.

## 4. Optional Genie space enrichment (UI)

The Genie REST API today does not accept `instructions`, `sample_questions`, or rich function metadata in the create payload. If you want to enrich the space with the recommended instructions and 10 sample questions, do it after running `03_genie_setup`:

1. Sidebar → **Genie** → **DISA Threat Intel (`<your-user>`)**.
2. Settings → **Instructions** → paste the text in `docs/docs/modules/03-genie.md`.
3. Settings → **Sample questions** → paste the 10 questions in the same file.

This is optional — the compound agent works without these enrichments.

## 5. Vocareum upload

The Vocareum-hosted version of the workshop bundles the notebooks + scripts. To upload:

```bash
export VOC_TOKEN="$(read -s -p 'Vocareum token: ' t; echo $t)"
export VOC_COURSE_ID="<course-id>"
export VOC_ASSIGNMENT_ID="<assignment-id>"
export VOC_PART_ID="<part-id>"

cd vocareum && ./upload.sh
```

The upload bundles the notebooks, the data directory, the courseware config, and the lifecycle Python scripts into three Vocareum targets (`private`, `scripts`, `docs`).

The Vocareum scripts include `vocareum/scripts/python/_dbacademy_vs_patch.py`, which sanitizes Vector Search endpoint names so dbacademy doesn't trip the 50-character Databricks limit when the Vocareum org prefix is long. See `vocareum/README.md`.

## 6. Compute sizing (for ~25 attendees)

| Resource | Size | Notes |
|---|---|---|
| Shared SQL warehouse | Small (4 DBU) | Serverless. Auto-stops after 10 min idle. One warehouse for all attendees. |
| Foundation model serving | Pay-per-token (Claude Haiku 4.5 + Sonnet 4.6) | No provisioning needed. |
| KA endpoint per attendee | Auto-sized | First-time provision ~10-20 min. |
| Agent endpoint per attendee | Small (1 concurrency) | Scale-to-zero enabled. First-time provision ~10-15 min. |
| Databricks App per attendee | Default | First-time provision + npm install ~5-10 min. |

Total budget for a 3-hour workshop: ~30 DBUs across all attendees.

## 7. Cleanup after workshop

The cleanest reset (drops every per-user schema in one shot, then deletes the per-user serving endpoints / KAs / Genie spaces / apps):

```python
%run ./_config

# Drop this user's schema (or loop over all attendees' schemas)
spark.sql(f"DROP SCHEMA IF EXISTS {BASE} CASCADE")

# Delete this user's serving endpoint, KA, app
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
try: w.serving_endpoints.delete(name=AGENT_ENDPOINT)
except Exception: pass
try: w.api_client.do("DELETE", f"/api/2.1/knowledge-assistants/{cfg_get('ka_id')}")
except Exception: pass
try: w.api_client.do("DELETE", f"/api/2.0/genie/spaces/{cfg_get('genie_space_id')}")
except Exception: pass
try: w.apps.delete(name=APP_NAME)
except Exception: pass
```

To reset everything for everyone, run as a workspace admin and iterate the per-user `cti_*` schemas under the catalog.
