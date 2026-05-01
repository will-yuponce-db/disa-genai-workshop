# Architecture

```
                  ┌──────────────────────────────────┐
                  │   Databricks App (React + Express)  │
                  │   /api/sql      /api/agent/step      │
                  └───────┬───────────────────┬──────────┘
                          │                   │
                          │ SQL warehouse     │ Model Serving
                          ▼                   ▼
            ┌────────────────────┐   ┌────────────────────────┐
            │ Unity Catalog       │   │  disa-cti-agent          │
            │ disa_workshop.*     │   │  (ResponsesAgent)        │
            │ - kev_catalog       │   └──────┬─────────────────┘
            │ - cves              │          │ tool calls
            │ - attack_techniques │   ┌──────┴───────┬──────────┬──────────────┐
            │ - affected_assets   │   ▼              ▼          ▼              ▼
            │ - parsed_advisories │  Genie       Knowledge   Fetch MCP   ai_parse_document
            │ Volume:             │  space       Assistant   (cisa.gov)  (PDFs in volume)
            │ raw_advisories/     │
            │ raw_stigs/          │
            └─────────────────────┘
```

## Components

### Unity Catalog
- **Catalog**: `disa_workshop`
- **Schema**: `threat_intel`
- **Tables**: `kev_catalog`, `cves`, `attack_techniques`, `attack_groups`, `affected_assets`, `parsed_advisories`, `structured_advisories`
- **Volumes**: `raw_advisories` (PDFs), `raw_stigs` (XCCDF XML), `ka_corpus` (combined KA source)

### Compound agent (`disa-cti-agent`)
- Mosaic AI `ResponsesAgent`
- Foundation model: Claude Sonnet 4.6 (configurable)
- 4 tools: Genie, Knowledge Assistant, Fetch URL, parse PDF
- Deployed to Model Serving with scale-to-zero

### App (Databricks App)
- React 18 + Vite + Tailwind + Recharts
- Express backend exposing `/api/sql` (read-only, allowlisted) and `/api/agent/step` (forwards to agent endpoint)
- Token forwarding via Databricks Apps resource injection

### Vocareum lifecycle
- `workspace_init.sh` provisions UC + seed data once per workspace
- `user_setup.sh` per-attendee on first lab entry
- `lab_setup.sh` resumes warehouse on lab re-entry
- `lab_end.sh` pauses warehouse on session end
