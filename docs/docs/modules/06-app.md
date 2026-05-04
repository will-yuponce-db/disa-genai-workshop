# Module 6 — Spin up an app

**Time**: 25 minutes

The repo no longer ships an app source tree. Pick any stock Databricks Apps template (Streamlit chat is the easiest), wire it to your per-user agent endpoint, deploy.

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

## Extending the template ad-hoc with Genie

Once the templated app is running, you can extend it without writing the boilerplate:

1. Ask Genie a question — e.g. *"top 10 vendors by KEV catalog count"*.
2. Click **View SQL** in Genie. Copy SQL + result-schema columns.
3. Paste both into Claude with a prompt like *"give me a Streamlit snippet that calls this SQL via WorkspaceClient.statement_execution and renders it as a bar chart"*.
4. Paste the snippet into the template's main file. Redeploy. Refresh.

Total time per added chart: about a minute.

[Open the notebook →](https://github.com/will-yuponce-db/disa-genai-workshop/blob/main/notebooks/06_deploy_app.ipynb)
