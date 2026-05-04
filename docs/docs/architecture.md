# Architecture

```
                  ┌──────────────────────────────────┐
                  │   Databricks App (React + Express)  │
                  │   /api/sql      /api/agent/step      │
                  └───────┬───────────────────┬──────────┘
                          │                   │
                          │ SQL warehouse     │ Model Serving
                          ▼                   ▼
            ┌─────────────────────────┐   ┌────────────────────────┐
            │ Unity Catalog            │   │  disa-cti-agent          │
            │ saf_aq_demo_catalog      │   │  (ResponsesAgent)        │
            │ .disa_threat_intel       │   └──────┬─────────────────┘
            │ - kev_catalog            │          │ tool calls
            │ - cves                   │   ┌──────┴───────┬──────────┬──────────────┐
            │ - attack_techniques      │   ▼              ▼          ▼              ▼
            │ - attack_groups          │  Genie       Knowledge   Fetch URL    ai_parse_document
            │ - affected_assets        │  space       Assistant   (allowlist)  (PDFs in volume)
            │ - parsed_advisories      │
            │ - structured_advisories  │
            │ - advisories (view)      │
            │ - _workshop_config       │
            │ Volumes:                  │
            │   raw_advisories/         │
            │   raw_stigs/              │
            │   ka_corpus/              │
            └─────────────────────────┘
```

## Components

### Unity Catalog

- **Catalog**: `saf_aq_demo_catalog`
- **Schema**: `disa_threat_intel`
- **Tables**: `kev_catalog`, `cves`, `attack_techniques`, `attack_groups`, `affected_assets`, `parsed_advisories`, `structured_advisories`, `advisories` (view), `_workshop_config`
- **Volumes**: `raw_advisories` (PDFs), `raw_stigs` (XCCDF text snippets), `ka_corpus` (combined KA source)

### `_workshop_config` table

A 2-column Delta table (`key STRING, value STRING`) that every notebook MERGE-INTOs as it produces an artifact:

| Key | Producer | Consumer |
|---|---|---|
| `catalog`, `schema`, `llm_endpoint` | `00_setup` | all |
| `warehouse_id` | `03_genie_setup` | `05_compound_agent`, `06_deploy_app` |
| `genie_space_id` | `03_genie_setup` | `05_compound_agent` |
| `ka_id`, `ka_endpoint` | `04_knowledge_assistant` | `05_compound_agent` |

This is what lets the workshop run end-to-end without anyone copying ids between cells.

### Compound agent (`disa-cti-agent`)

- Mosaic AI `ResponsesAgent` (mlflow.pyfunc)
- Foundation model: Claude Sonnet 4.6 (configurable via `_workshop_config.llm_endpoint`)
- 4 tools: Genie, Knowledge Assistant, Fetch URL, parse PDF
- Deployed to Model Serving with scale-to-zero
- Routes all serving calls through `WorkspaceClient.api_client.do(...)` so the same code runs under PAT, OAuth, or M2M auth

### App (Databricks App)

- React 18 + Vite + Tailwind + Recharts
- Express backend exposing `/api/sql` (read-only, allowlisted to the configured warehouse) and `/api/agent/step` (forwards to `disa-cti-agent`)
- Token forwarding via Databricks Apps resource injection
- `app.yaml` is patched at deploy time by `06_deploy_app.ipynb` to use the live `warehouse_id` from `_workshop_config`

### Vocareum lifecycle

- `vocareum/scripts/python/_dbacademy_vs_patch.py` — sanitizes Vector Search endpoint names so dbacademy doesn't trip the 50-char limit when the Vocareum org prefix is long (e.g., `vc_2_0_c4a2c694org550_234_<user>`).
- `workspace_init.sh` provisions UC + seed data once per workspace
- `user_setup.sh` per-attendee on first lab entry — imports the patched `_dbacademy_vs_patch` before calling `voc_init().user_setup(...)`
- `lab_setup.sh` resumes warehouse on lab re-entry
- `lab_end.sh` pauses warehouse on session end
