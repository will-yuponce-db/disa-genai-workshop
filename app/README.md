# DISA CTI App

The Databricks App that embeds the compound CTI agent + a chart playground for the live vibe-code demo.

## Local dev

```bash
npm install

# Required env vars (read by backend/createApp.js)
export DATABRICKS_HOST="https://<your-workspace>.cloud.databricks.com"
export DATABRICKS_TOKEN="..."
export DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/<warehouse-id>"
export DATABRICKS_AGENT_ENDPOINT="disa-cti-agent"

npm run dev   # web on :5173, api on :8000
```

## Deploy to Databricks Apps

1. Update `app.yaml` with your warehouse ID.
2. Build and upload:
   ```bash
   npm run build
   databricks workspace import-dir . /Workspace/Users/${USER}@databricks.com/disa-genai-workshop/app --overwrite
   databricks apps deploy disa-cti --source-code-path /Workspace/Users/${USER}@databricks.com/disa-genai-workshop/app
   ```

## Architecture

```
React (Vite, Tailwind, Recharts)
  -> /api/sql           (Express) -> SQL warehouse via @databricks/sql
  -> /api/agent/step    (Express) -> POST disa-cti-agent /invocations
                                       (compound agent: Genie + KA + Fetch + parse_pdf)
```

## Vibe-code workflow

1. Open Genie, ask a question, click View SQL.
2. Open `prompts/vibe_code_component.md` (one level up).
3. Paste SQL + schema + goal + name into the prompt.
4. Send to Claude. Save the returned `.tsx` to `src/pages/<Name>.tsx`.
5. Add a `<Route path="/charts/<slug>" element={<Name />} />` in `src/App.tsx`.
6. The chart appears.
