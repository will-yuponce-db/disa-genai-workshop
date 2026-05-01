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

## Why this is the workshop's punch line

Two minutes of work — paste, prompt, save, refresh — turns into a working analyst tool. The pattern generalizes: any Genie question becomes a polished UI in the time it takes to explain what you wanted.

The take-home prompt is in [`prompts/vibe_code_component.md`](https://github.com/your-handle/disa-genai-workshop/blob/main/prompts/vibe_code_component.md). See the [Vibe-code prompt](../vibe-code.md) page for the prompt copy and a worked example.

## Architecture recap

```
React (Tailwind, Recharts)  ←  Genie SQL via prompt template  ←  Genie space
       │
       ▼
/api/sql  →  warehouse  →  rendered chart
/api/agent/step  →  disa-cti-agent  →  Genie + KA + Fetch + parse_pdf
```
