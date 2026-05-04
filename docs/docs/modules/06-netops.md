# Module 6 — NetOps log analysis with `ai_query` (bulk inference)

**Time**: 20 minutes

This module sits between 5 (compound agent build) and 6 (app deploy). It demonstrates the *other* shape of GenAI work on Databricks: **structured extraction at scale** via `ai_query` over a column.

The Knowledge Assistant in Module 4 retrieves doctrine. `ai_query` aggregates. A NOC analyst wants both — and `ai_query` is the right primitive for triaging email digests, ticket dumps, syslog forwarders, and change-request feeds at scale.

## Real, public data — no synthetic logs

Source: the [`outages@outages.org` mailing list archive](https://puck.nether.net/pipermail/outages/) — every monthly archive is a public mbox file with real network-operator reports of real incidents (Zoom DNS outages, Lumen fiber cuts, Cloudflare config rollbacks, IPAWS test reactions, peering disputes, etc.). The notebook pulls the last 12 monthly archives.

## What the notebook does

1. **Discover available archives** by parsing the index page (the list isn't strictly contiguous — volunteer-run).
2. **Pull and parse mbox** with the standard library, strip quoted replies and signatures, land each message as a row in `<schema>.netops_outage_messages`.
3. **One `ai_query` SQL statement** classifies every row in parallel:

   ```sql
   CREATE OR REPLACE TABLE <schema>.netops_outages_structured AS
   SELECT message_id, subject,
          ai_query(
            'databricks-claude-haiku-4-5',
            CONCAT('You are a NOC analyst. Extract incident attributes...', subject, body),
            responseFormat => '<json schema>'
          ) AS extract
   FROM <schema>.netops_outage_messages
   ```

   The same prompt + JSON schema applied to every row. No Python loop. Mosaic AI Model Serving handles the parallelism.

4. **Flatten to a queryable view** `<schema>.netops_outages` with `root_cause`, `severity`, `affected_providers`, `affected_regions`, `summary`, etc.
5. **Register a UC SQL function** `<schema>.recent_outages(provider_query, days)` so the compound agent (Module 5) gets a fifth tool: *"any recent BGP outages affecting Lumen?"*

## Order to run

00 → 01 → 02 → 03 → 04 → 05 → **5b** → 06.

Module 5's compound agent picks up the netops table automatically through `_workshop_config`, so re-deploying the agent after running module 6 gives it real outage data to query. Skipping module 6 is fine — the agent's other four tools still work.

## Sample output (validated dry run)

| metric | value |
|---|---|
| messages parsed | 367 |
| classified as outage reports | 231 |
| top root causes | DNS (27), peering (19), BGP (15), power (12), fiber-cut (11), routing, DDoS, config-change |
| sample | "Zoom Outage 4/16/25 — domain registry serverHold caused DNS resolution failures" |

## The reusable pattern

| Use case | Source | `ai_query` extracts |
|---|---|---|
| Outage triage | mailing list, ticket dump | this module |
| Change-request risk grading | ServiceNow CRs | risk_class, blast_radius, rollback_plan_present |
| Syslog noise reduction | Splunk / OpenSearch | event_class, severity, host_role |
| Vendor PSIRT triage | RSS/Atom feeds | affected_models, exploitability, has_workaround |

Same shape every time: one prompt, one JSON schema, applied to a column.

[Open the notebook →](https://github.com/will-yuponce-db/disa-genai-workshop/blob/main/notebooks/06_netops_ai_query.ipynb)
