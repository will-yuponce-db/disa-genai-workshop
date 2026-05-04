# Module 2 — Foundation Models (programmatic Playground)

**Time**: 15 minutes

In the original Vocareum-style version of this workshop, Module 2 was a click-through tour of the **AI Playground** UI. This version replaces it with `notebooks/02_ai_playground.ipynb` so the whole workshop runs cell-by-cell without UI excursions.

If you want to mirror the same exercises in the AI Playground UI for an audience that prefers visual side-by-side comparisons, the notebook ends with a section explaining which sidebar pages do what.

## What the notebook does

| Cell | What it shows |
|---|---|
| 1 | List foundation model endpoints reachable in this workspace (via `WorkspaceClient.serving_endpoints.list`). |
| 2 | Call `ai_query` from SQL — the simplest way to use a foundation model in a query. |
| 3 | Call the chat-completions API directly via `WorkspaceClient.api_client.do(...)`. Useful when you want full control over messages, tools, temperature. |
| 4 | Side-by-side latency + quality comparison: Haiku 4.5 vs Sonnet 4.6 on the same prompt. Same one you'd run in the Playground's "compare two models" pane. |
| 5 | Tool-calling preview: register a function tool, ask a question that should trigger the call, inspect the `tool_calls` field in the response. Foreshadows Module 5. |

## When to choose the Playground UI instead

The notebook covers 100% of the Playground's behavior, but the UI has nicer ergonomics for exploration:

- **Side-by-side comparison**: AI Playground → "Compare" toggle. Two panes, drag-and-drop prompt sharing.
- **Prompt versioning**: AI Playground → Save → name the version → export to notebook cell.
- **Inline parameter sliders**: temperature, max tokens, top_p (the notebook hardcodes these for repeatability).

If you want to demo any of the above in front of an audience: open the AI Playground (sidebar → AI Playground), pick `databricks-claude-sonnet-4-6`, and paste the prompts from the notebook.

## Why this matters

The Playground (or this notebook) is where prompt engineering happens. Once a prompt works, it's a one-line change to deploy it as an `ai_query` in SQL or a model-serving call in your agent (Module 5).

[Open the notebook →](https://github.com/your-handle/disa-genai-workshop/blob/main/notebooks/02_ai_playground.ipynb)
