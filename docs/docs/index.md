# DISA GenAI Workshop

A **2.5 hour, hands-on Databricks workshop** for cyber threat intelligence and vulnerability management on the Mosaic AI stack.

> Audience: DISA analysts and engineers (mixed). Hosted on Vocareum. All data is unclassified and public open source.

## What you'll build

By the end of the workshop you will have built and deployed a **compound AI agent for cyber threat intelligence** that can answer questions like:

> *"A new CISA advisory just dropped at this URL. Find related KEV entries, tell me which STIG controls apply, and summarize the operational impact."*

It does this by orchestrating four tools — Genie, a Knowledge Assistant, a Fetch tool for live web pulls, and `ai_parse_document` — behind a single chat interface in a Databricks App.

The workshop closes with a **live vibe-code demo**: paste a Genie-generated SQL query into Claude using a templated prompt and watch a working React chart appear in the deployed app.

## How the notebooks chain

Every module is a runnable notebook. Each one writes its outputs (Genie space id, KA endpoint, warehouse id, etc.) into a shared Delta table — `main.cti_<user>._workshop_config` — that downstream notebooks read on startup. The attendee never copies an ID from one notebook to another, and never has to leave the notebook for the Databricks UI.

```
00_setup ─┐
01_ingest │
02_play   ├── all read & write _workshop_config ──→ 06_deploy_app
03_genie  │
04_ka     │
05_agent ─┘
```

## Module overview

| # | Module | Time |
|---|---|---|
| [0](modules/00-setup.md) | Workspace bootstrap (catalog, KEV/CVE/ATT&CK ingest) | 10m |
| [1](modules/01-ingest.md) | Document ingest with AI Functions | 30m |
| [2](modules/02-playground.md) | Foundation models (programmatic Playground) | 15m |
| [3](modules/03-genie.md) | Genie space over CVE / KEV / STIG | 25m |
| [4](modules/04-knowledge-assistant.md) | Knowledge Assistant (Agent Bricks) | 20m |
| [5](modules/05-compound-agent.md) | Compound agent | 30m |
| [6](modules/06-app.md) | App embed + live vibe-code | 25m |

## Public datasets

| Dataset | Source |
|---|---|
| CISA KEV catalog | [cisa.gov/known-exploited-vulnerabilities-catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) |
| NIST NVD | NVD 2.0 REST API |
| MITRE ATT&CK | STIX 2.1 JSON |
| CISA advisories | cisa.gov/news-events |
| DoD STIGs | [public.cyber.mil](https://public.cyber.mil) |

## One-time UI prerequisites

These are the **only** clicks the instructor (not attendees) needs to do, once per workspace, before running the notebooks:

1. **Enable Agent Bricks** on the workspace (Workspace settings > Previews > Agent Bricks). Per-workspace toggle, controlled by a workspace admin. Without it, Module 4 cannot create a Knowledge Assistant.
2. **Enable Genie** (Workspace settings > Previews > AI/BI Genie). Default-on in newer workspaces.
3. **Enable Vector Search and Mosaic AI Model Serving** (default-on).
4. Confirm a serverless SQL warehouse exists (`SHOW WAREHOUSES`).

Everything else — catalog creation, schema, volume creation, Genie space, Knowledge Assistant, agent endpoint, app — is created by the notebooks themselves.
