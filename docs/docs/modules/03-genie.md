# Module 3 — Genie Space

**Time**: 25 minutes

## What you'll build

A Genie space over the CVE / KEV / STIG / asset tables. Attendees ask English questions, Genie writes the SQL.

## Configuration

| Setting | Value |
|---|---|
| Display name | DISA Threat Intel |
| Datasets | `kev_catalog`, `cves`, `affected_assets`, `attack_techniques`, `attack_groups` |
| Functions | `lookup_cve(cve)`, `assets_for_product(vendor, product)` |
| Sample questions | 10 curated (see notebook) |

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
