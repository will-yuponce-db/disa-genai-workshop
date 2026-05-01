# Vibe-Code Prompt

The reusable Claude prompt that turns Genie SQL into a working React component for the Databricks App.

## How to use

1. Ask Genie a question.
2. Click **View SQL**. Copy the SQL.
3. Copy the result schema (column names + types).
4. Paste both into the prompt below. Fill in the goal and component name.
5. Send to Claude. Save the returned `.tsx` to `app/src/pages/<Name>.tsx`. Add a route.
6. `npm run dev` reloads automatically.

## The prompt

````
You are generating a single React + TypeScript component for a Databricks App.

CONTEXT
- App framework: React 18 + Vite + TypeScript
- Backend endpoint: POST /api/sql with body {sql: string} returns {rows: any[], schema: ColumnSchema[]}
  where ColumnSchema = {name: string, type: string}
- Charting: Recharts (already installed)
- Styling: Tailwind CSS, components from src/components/Card.tsx (Card, CardHeader, CardTitle, CardDescription, CardContent)
- File location: app/src/pages/<ComponentName>.tsx
- Theme: cyber threat intel — favor red/amber/green for severity, blues for neutral counts.

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
- The SQL must be embedded as a const string at the top of the component.
- Use React hooks. No class components.
- Handle loading, error, and empty (rows.length === 0) render states.
- Use Recharts <ResponsiveContainer> at width="100%" height={360}.
- Wrap the chart in <Card>/<CardHeader>/<CardTitle>/<CardDescription>/<CardContent>.
- Use Tailwind. No inline style objects unless required by Recharts.
- Type the row shape based on the schema.
- Export default the component.
- No TODO comments, placeholder data, stub functions, or console.log.

OUTPUT
Return ONLY the .tsx file content. No prose, no markdown fences, no explanation.
````

## Worked example

**Genie question**: *"Top 10 vendors with the most KEV-listed CVEs."*

```sql
SELECT vendor, COUNT(*) AS cve_count
FROM disa_workshop.threat_intel.kev_catalog
GROUP BY vendor
ORDER BY cve_count DESC
LIMIT 10
```

**Schema**:
```
vendor: string
cve_count: bigint
```

**Goal**: `horizontal bar chart of CVE count by vendor, top 10`

**Name**: `KevByVendorChart`

Run the prompt → drop the result at `app/src/pages/KevByVendorChart.tsx` → add `<Route path="/charts/kev-by-vendor" element={<KevByVendorChart />} />` → reload.
