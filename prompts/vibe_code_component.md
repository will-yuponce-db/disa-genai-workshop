# Vibe-Code Prompt: Genie SQL → React Component

A copy-paste prompt that turns any Genie-generated SQL query into a working, drop-in React component for the Databricks App in `/app`. Use this during the workshop's live demo and take it home for your own apps.

## How to use

1. Ask a question in your Genie space.
2. Click **"View SQL"** in Genie. Copy the SQL query.
3. Click the **"Result schema"** tab (or look at the column headers + types). Copy them.
4. Paste both into the prompt below, fill in the goal and component name, send to Claude.
5. Claude returns a single `.tsx` file. Save it to `app/src/pages/<Name>.tsx` and add a route.
6. `npm run dev` reloads automatically.

## The prompt

> Copy everything between the lines and paste into Claude (Sonnet 4.6 or newer recommended).

---

```
You are generating a single React + TypeScript component for a Databricks App.

CONTEXT
- App framework: React 18 + Vite + TypeScript
- Backend endpoint: POST /api/sql with body {sql: string} returns {rows: any[], schema: ColumnSchema[]}
  where ColumnSchema = {name: string, type: string}
- Charting: Recharts (already installed)
- Styling: Tailwind CSS, components from shadcn/ui (Card, CardHeader, CardTitle, CardDescription, CardContent are available)
- File location: app/src/pages/<ComponentName>.tsx
- The app is themed for cyber threat intel — favor red/amber/green semantic colors for severity, blues for neutral counts.

INPUTS
- Genie-generated SQL:
<<<SQL
<paste SQL here>
SQL>>>

- Result schema (one column per line, "name: type"):
<<<SCHEMA
<paste columns + types here>
SCHEMA>>>

- Visualization goal (one sentence):
<<<GOAL
<e.g. "horizontal bar chart of CVE count grouped by vendor, sorted descending, top 15 only">
GOAL>>>

- Component name (PascalCase):
<<<NAME
<e.g. CveByVendorChart>
NAME>>>

REQUIREMENTS
- Fetch on mount via fetch('/api/sql', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({sql: SQL}) })
- The SQL must be embedded as a const string at the top of the component, not constructed at runtime.
- Use React hooks (useState, useEffect). No class components.
- Handle three render states: loading, error, empty (rows.length === 0).
- Use Recharts <ResponsiveContainer> at width="100%" height={360}.
- Wrap the chart in <Card> with <CardHeader> containing a 2-4 word <CardTitle> and a 1-line <CardDescription> derived from the goal.
- Use Tailwind for any custom styling. No inline style objects unless required by Recharts.
- Type the row shape based on the schema. Use `Record<string, unknown>` only as a last resort.
- Export default the component.
- No TODO comments, no placeholder data, no stub functions, no console.log.

OUTPUT
Return ONLY the .tsx file content. No prose, no markdown fences, no explanation. Begin with the imports.
```

---

## Worked example (use this to rehearse before the workshop)

**Genie question**: *"Show me the top 10 vendors with the most KEV-listed CVEs, sorted by count descending."*

**SQL Genie generates** (paste into the prompt):

```sql
SELECT vendor, COUNT(*) AS cve_count
FROM disa_workshop.threat_intel.kev_catalog
GROUP BY vendor
ORDER BY cve_count DESC
LIMIT 10
```

**Schema** (paste into the prompt):

```
vendor: string
cve_count: bigint
```

**Goal**: `horizontal bar chart of CVE count by vendor, top 10`

**Name**: `KevByVendorChart`

Run the prompt → drop the resulting file at `app/src/pages/KevByVendorChart.tsx` → add `<Route path="/charts/kev-by-vendor" element={<KevByVendorChart />} />` to your router → reload.

## Tips

- **Stay deterministic.** Don't let the model invent columns. The schema block is load-bearing.
- **Pin the SQL.** Embedding the SQL string as a const lets attendees see exactly what's running. Better than building it at runtime.
- **Iterate small.** If the first chart isn't right, edit the goal one sentence at a time and rerun. Don't ask the model to "make it better" — give it a measurable change.
- **Watch for prompt drift.** If you swap the chart library or add auth headers, update the CONTEXT block, not the inputs.

## Why this works

The prompt fully constrains the model's degrees of freedom: framework, file location, fetch shape, chart library, render-state contract, and output format. The model only chooses the chart type, color encoding, and column mapping — and even those are pinned by the goal. That means you can hand this prompt to a non-engineer and they will get a working component on the first try.
