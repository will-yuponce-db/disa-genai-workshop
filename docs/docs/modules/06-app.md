# Module 6 — App embed + live vibe-code

**Time**: 25 minutes

## What we'll demo

1. **The app**: a Databricks App with React + Vite, an embedded chat to `disa-cti-agent`, and a `/charts` page that's empty at the start.
2. **Live vibe-code**:
   - Ask Genie: *"top 10 vendors by KEV catalog count"*.
   - Click **View SQL**. Copy SQL + schema.
   - Open `prompts/vibe_code_component.md`. Paste into the prompt template. Send to Claude.
   - Save the returned `.tsx` to `app/src/pages/KevByVendorChart.tsx`.
   - Add `<Route path="/charts/kev-by-vendor" element={<KevByVendorChart />} />` to `App.tsx`.
   - The chart appears in the running dev server.

## Deployment

`notebooks/06_deploy_app.ipynb` collapses the four-shell-command deploy into a single notebook run. It:

1. Reads `warehouse_id` from `_workshop_config` so `app.yaml` always points at the live warehouse.
2. Builds `app/dist/` if it isn't already committed.
3. Patches a copy of `app.yaml` in `/tmp` with the live warehouse id (the repo's `app.yaml` keeps a default for local development).
4. Syncs the staged app to `/Workspace/Users/<you>/disa-genai-workshop-app`.
5. Calls `databricks apps create disa-cti` (idempotent — tolerates "already exists").
6. Calls `databricks apps deploy disa-cti --source-code-path /Workspace/Users/<you>/disa-genai-workshop-app`.
7. Prints the live URL.

App provisioning + first deploy typically takes 5-10 minutes (workspace pulls Node.js dependencies and starts the Express server).

## What the notebook leaves to the UI

- **Sidebar → Apps → disa-cti** — confirm `app_status: AVAILABLE` and `compute_status: ACTIVE`. Click the URL to open.
- **Logs panel** — useful when a deploy fails (look for `npm ERR!` or "endpoint not found" if the agent isn't ready).

The vibe-code workflow itself is interactive by design: the attendee writes a Genie question, copies the generated SQL into the take-home prompt, and pastes the resulting React file back into the app. This is the workshop's payoff and isn't automatable.

## Why this is the workshop's punch line

Two minutes of work — paste, prompt, save, refresh — turns into a working analyst tool. The pattern generalizes: any Genie question becomes a polished UI in the time it takes to explain what you wanted.

The take-home prompt is in [`prompts/vibe_code_component.md`](https://github.com/will-yuponce-db/disa-genai-workshop/blob/main/prompts/vibe_code_component.md). See the [Vibe-code prompt](../vibe-code.md) page for the prompt copy and a worked example.

## Architecture recap

```
React (Tailwind, Recharts)  ←  Genie SQL via prompt template  ←  Genie space
       │
       ▼
/api/sql  →  warehouse  →  rendered chart
/api/agent/step  →  disa-cti-agent  →  Genie + KA + Fetch + parse_pdf
```

[Open the notebook →](https://github.com/will-yuponce-db/disa-genai-workshop/blob/main/notebooks/06_deploy_app.ipynb)
