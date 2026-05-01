# Module 2 — AI Playground Walkthrough

**Time**: 15 minutes (live demo, no notebook)

## What we'll cover

The AI Playground is the fastest way to compare models, iterate on prompts, and verify tool-calling behavior — without writing code.

### 1. Side-by-side comparison
- Open two panes: Llama 4 Maverick vs Claude Sonnet 4.6.
- Paste in the prompt from Module 1's `ai_query` and compare the structured outputs.
- Discuss which model is more reliable for structured extraction at this scale.

### 2. Tool calling
- Add the `lookup_cve` SQL function (registered in Module 3) as a tool.
- Ask: *"Tell me about CVE-2024-21412"* — watch the model decide to call `lookup_cve`.
- Discuss when tool calling is the right pattern vs. one-shot RAG.

### 3. Prompt versioning
- Save the working prompt as a version.
- Show how to export to a notebook cell (handy for productionizing).

## Why this matters

The Playground is where prompt engineering happens. Once a prompt works there, it's a one-line change to deploy it as an `ai_query` in SQL or a model-serving endpoint.
