# Module 6 — Spin up an app + vibe-code

**Time**: 25 minutes

The repo no longer ships an app source tree. Pick any stock Databricks Apps template (Streamlit chat is the easiest), then vibe-code on top.

## Steps

1. Sidebar → **Apps** → **Create app**.
2. Pick the **Streamlit chat** template (or any starter — Dash, Gradio, FastAPI all work).
3. Name it `disa-cti-<your-suffix>`.
4. Add a **serving-endpoint** resource pointing at your per-user agent endpoint from Module 5 (alias `agent-endpoint`).
5. Add a **SQL warehouse** resource pointing at the workspace's serverless warehouse (alias `sql-warehouse`).
6. Set env vars:
    - `DATABRICKS_AGENT_ENDPOINT = disa-cti-agent-<user>`
    - `DATABRICKS_CATALOG = <your-catalog>`
    - `DATABRICKS_SCHEMA = cti_<user>`
7. Click **Deploy**.

`notebooks/06_deploy_app.ipynb` prints all of these per-user values for copy-paste.

## Live vibe-code

Once the templated app is running:

1. Ask Genie a question — e.g. *"top 10 vendors by KEV catalog count"*.
2. Click **View SQL** in Genie. Copy SQL + result-schema columns.
3. Open `prompts/vibe_code_component.md`. Paste SQL + schema into the prompt template.
4. Send to Claude. It returns a snippet for the framework you picked.
5. Paste it into the template's main file. Redeploy. Refresh.

Total time per added chart: about a minute.

## Why this module is shorter than it looks

The whole point is the speed. The template gives you a chat box wired to your agent in two clicks; the vibe-code prompt turns Genie SQL into a working chart in a minute. The interesting work is the agent (Module 5) and the data behind it (00, 01, 03, 04, 5b).

[Open the notebook →](https://github.com/will-yuponce-db/disa-genai-workshop/blob/main/notebooks/06_deploy_app.ipynb)
