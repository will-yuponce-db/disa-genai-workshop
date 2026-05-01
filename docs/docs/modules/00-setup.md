# Module 0 — Setup

**Time**: 10 minutes (instructor runs once on Vocareum; attendees just sign in)

## Attendee setup

1. Open the Vocareum lab page from the email you received.
2. Click **Start Lab**. Vocareum will provision your Databricks workspace user.
3. The lab portal redirects you to the Databricks workspace.
4. Confirm your workspace tour by:
   - Clicking **Catalog** in the sidebar — you should see `disa_workshop.threat_intel`.
   - Clicking **SQL Warehouses** — confirm `shared_warehouse` is **Running** or **Starting**.
   - Clicking **Compute > Serving** — confirm there's a model serving endpoint reachable.

## Instructor setup

Run `notebooks/00_setup.ipynb` once before the workshop. It:

1. Creates `disa_workshop.threat_intel` catalog/schema/volumes
2. Pulls live CISA KEV catalog (~1,200 entries)
3. Pulls NIST NVD CVEs from 2024–2025 (~30 MB)
4. Pulls the MITRE ATT&CK STIX bundle (~300 techniques, ~150 groups)
5. Generates 500 synthetic DoD assets for join queries
6. Uploads ~20 CISA advisory PDFs to the `raw_advisories` volume

[See the notebook on GitHub →](https://github.com/your-handle/disa-genai-workshop/blob/main/notebooks/00_setup.ipynb)
