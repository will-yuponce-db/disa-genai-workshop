# Vibe-Code Prompt

The reusable Claude prompt that turns a Genie SQL query into a working chart snippet for whatever Databricks Apps template you spun up in Module 6.

The full prompt and a worked example live in [`prompts/vibe_code_component.md`](https://github.com/will-yuponce-db/disa-genai-workshop/blob/main/prompts/vibe_code_component.md). The version in the repo is shaped for a Streamlit template; if you picked Dash or Gradio, swap the framework name and Claude follows.

## How to use

1. Ask Genie a question.
2. Click **View SQL** in Genie. Copy the SQL.
3. Copy the result schema (column names + types).
4. Paste both into the prompt template, fill in the chart goal, send to Claude.
5. Paste Claude's returned snippet into the template's main file (e.g. `app.py` for Streamlit). Redeploy. Refresh.

Total time per chart: about a minute.

## What the prompt asks Claude to produce

A self-contained code snippet that:

- Calls the warehouse via `WorkspaceClient.statement_execution.execute_statement(...)`.
- Caches results.
- Handles the empty-result case gracefully.
- Casts numeric columns from string before charting (warehouse statement results come back as strings).

No theming or styling — keep it minimal so the demo lands the speed argument, not the prettiness.

## Why this is the workshop's punch line

The agent (Module 5) is the sophisticated part. Module 6 is the *easy* part — and that's the point. Once Genie + agent + warehouse are in place, building UI is two minutes of paste-prompt-save. The pattern generalizes to any Genie question becoming a polished chart in the time it takes to explain what you wanted.
