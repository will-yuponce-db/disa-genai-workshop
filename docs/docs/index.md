# DISA GenAI Workshop

A **2.5 hour, hands-on Databricks workshop** for cyber threat intelligence and vulnerability management on the Mosaic AI stack.

> Audience: DISA analysts and engineers (mixed). Hosted on Vocareum. All data is unclassified and public open source.

## What you'll build

By the end of the workshop you will have built and deployed a **compound AI agent for cyber threat intelligence** that can answer questions like:

> *"A new CISA advisory just dropped at this URL. Find related KEV entries, tell me which STIG controls apply, and summarize the operational impact."*

It does this by orchestrating four tools — Genie, a Knowledge Assistant, a Fetch MCP for live web pulls, and `ai_parse_document` — behind a single chat interface in a Databricks App.

The workshop closes with a **live vibe-code demo**: paste a Genie-generated SQL query into Claude using a templated prompt and watch a working React chart appear in the deployed app.

## Story

```
A new CISA advisory drops.
  ↓ Parse the PDF                  (ai_parse_document)
  ↓ Match CVEs against KEV         (Genie)
  ↓ Find applicable STIG controls  (Knowledge Assistant)
  ↓ Pull live updates              (Fetch MCP)
  ↓ Compound agent ties it all together
  ↓ Embedded in a Databricks App you extend with vibe-coded components
```

## Module overview

| # | Module | Time |
|---|---|---|
| [0](modules/00-setup.md) | Vocareum sign-in + workspace tour | 10m |
| [1](modules/01-ingest.md) | Document ingest with AI Functions | 30m |
| [2](modules/02-playground.md) | AI Playground walkthrough | 15m |
| [3](modules/03-genie.md) | Genie space over CVE / KEV / STIG | 25m |
| [4](modules/04-knowledge-assistant.md) | Knowledge Assistant (Agent Bricks) | 20m |
| [5](modules/05-compound-agent.md) | Compound agent + Fetch MCP | 30m |
| [6](modules/06-app.md) | App embed + live vibe-code | 25m |

## Public datasets

| Dataset | Source |
|---|---|
| CISA KEV catalog | [cisa.gov/known-exploited-vulnerabilities-catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) |
| NIST NVD | NVD JSON API |
| MITRE ATT&CK | STIX 2.1 JSON |
| CISA advisories | cisa.gov/news-events |
| DoD STIGs | [public.cyber.mil](https://public.cyber.mil) |
