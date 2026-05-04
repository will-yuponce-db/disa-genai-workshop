# Module 3 — Genie Space

**Time**: 25 minutes

## What you'll build

A Genie space over the CVE / KEV / STIG / asset tables. Attendees ask English questions, Genie writes the SQL.

`notebooks/03_genie_setup.ipynb` creates the space programmatically via the **`POST /api/2.0/genie/spaces`** REST endpoint. The space id is persisted to `_workshop_config` so Module 5's compound agent can use it without anyone copying an id between cells.

## What the notebook configures

| Setting | Value |
|---|---|
| Display name | `DISA Threat Intel` |
| Datasets | `kev_catalog`, `cves`, `affected_assets`, `attack_techniques`, `attack_groups` |
| Helper SQL functions | `lookup_cve(cve)`, `assets_for_product(vendor, product)` |
| Warehouse | the first serverless warehouse in the workspace |

The two helper SQL functions are created in cells 2-3 of the notebook (`CREATE OR REPLACE FUNCTION ... RETURNS TABLE`). The Genie space picks them up automatically once they're attached.

## What the notebook leaves to the UI

The Genie REST API today accepts the table list and warehouse but **does not** accept rich `instructions`, `sample_questions`, or `function_identifiers` in the create payload. The notebook prints the recommended values and the Genie space URL; if you want to enrich the space, open it in the UI and:

1. **Sidebar → Genie → DISA Threat Intel.**
2. Settings → **Instructions** — paste the text below.
3. Settings → **Sample questions** — paste the 10 questions below.
4. Settings → **Functions** — confirm `lookup_cve` and `assets_for_product` are listed (they auto-attach because they live in the same schema).

This is optional. The compound agent in Module 5 works without these enrichments.

## Recommended instructions

```text
You are a cyber threat intelligence analyst assistant for DISA.

Vocabulary:
- KEV = CISA Known Exploited Vulnerabilities catalog. Entries here are actively exploited in the wild.
- CVE = Common Vulnerabilities and Exposures, format CVE-YYYY-NNNNN.
- CVSS = severity score 0.0 - 10.0. Critical >= 9.0, High >= 7.0.
- Affected assets are joined on vendor + product columns.
- The kev_catalog table uses column `vendorProject` for vendor (NOT `vendor`).
- Environments: NIPRNet (unclass), SIPRNet (secret), JWICS (TS).

When asked about "actively exploited" or "high-priority" CVEs, prefer the KEV catalog.
When asked about asset exposure, join CVEs/KEV to affected_assets via vendor + product.
Always cite CVE IDs and date ranges in your answer.
```

## Sample questions

1. Which KEV-listed CVEs were added in the last 30 days?
2. Show CVEs with CVSS > 9 affecting Microsoft products in our inventory.
3. Top 10 vendors by KEV catalog entry count.
4. Which SIPRNet hosts run products affected by 2025 KEV additions?
5. How many CVEs in 2025 have attack vector NETWORK and severity HIGH+?
6. Which DoD orgs own the most assets exposed to KEV?
7. Compare 2024 vs 2025 CVE counts.
8. Show Cisco IOS XE CVEs and the assets running it.
9. Which assets haven't been patched in 60+ days?
10. Median CVSS of KEV-listed CVEs?

## Vibe-code prep

Pick one of the sample questions, ask Genie, click **View SQL**, copy the SQL + the result schema. You'll use them in [Module 6](06-app.md).

[Open the notebook →](https://github.com/your-handle/disa-genai-workshop/blob/main/notebooks/03_genie_setup.ipynb)
