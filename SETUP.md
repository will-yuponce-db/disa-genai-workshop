# Setup Guide (Instructor / Vocareum Admin)

This guide walks an instructor or Vocareum admin through provisioning a workspace for the DISA GenAI workshop.

## 1. Workspace prerequisites

The host Databricks workspace must have the following enabled:

| Capability | How to verify |
|---|---|
| Unity Catalog | `SHOW CATALOGS` shows `system` and at least one workspace catalog |
| Mosaic AI Model Serving | Workspace > Serving > "Create endpoint" is available |
| Agent Bricks | Workspace > Agents > Knowledge Assistant tile is visible |
| Genie | Workspace > Genie > "New space" is available |
| Vector Search | Workspace > Compute > Vector Search endpoints |
| AI Functions | `SELECT ai_query('databricks-meta-llama-3-3-70b-instruct', 'hello')` runs |
| Serverless compute | Workspace > Compute > Serverless tab |

## 2. Catalog and schema

```sql
CREATE CATALOG IF NOT EXISTS disa_workshop;
CREATE SCHEMA IF NOT EXISTS disa_workshop.threat_intel;
CREATE VOLUME IF NOT EXISTS disa_workshop.threat_intel.raw_advisories;
CREATE VOLUME IF NOT EXISTS disa_workshop.threat_intel.raw_stigs;
```

Grant attendees `USE CATALOG`, `USE SCHEMA`, `SELECT`, `READ VOLUME`:

```sql
GRANT USE CATALOG ON CATALOG disa_workshop TO `workshop-attendees`;
GRANT USE SCHEMA ON SCHEMA disa_workshop.threat_intel TO `workshop-attendees`;
GRANT SELECT ON SCHEMA disa_workshop.threat_intel TO `workshop-attendees`;
GRANT READ VOLUME ON VOLUME disa_workshop.threat_intel.raw_advisories TO `workshop-attendees`;
GRANT READ VOLUME ON VOLUME disa_workshop.threat_intel.raw_stigs TO `workshop-attendees`;
```

## 3. Run `notebooks/00_setup.ipynb`

This downloads the public datasets, lands the seed Delta tables, and uploads ~20 CISA advisory PDFs to the volume.

Run as a workspace admin so grants succeed.

## 4. Vocareum upload

```bash
export VOC_TOKEN="$(read -s -p 'Vocareum token: ' t; echo $t)"
export VOC_COURSE_ID="<course-id>"
export VOC_ASSIGNMENT_ID="<assignment-id>"
export VOC_PART_ID="<part-id>"

cd vocareum && ./upload.sh
```

The upload bundles the notebooks, the data directory, the courseware config, and the lifecycle Python scripts into three Vocareum targets (`private`, `scripts`, `docs`).

## 5. Deploy the app (optional, for live vibe-code demo)

```bash
cd app
npm install
npm run build

databricks workspace import-dir . /Workspace/Users/${USER}@databricks.com/disa-genai-workshop/app --overwrite
databricks apps deploy disa-cti \
  --source-code-path /Workspace/Users/${USER}@databricks.com/disa-genai-workshop/app
```

Update `app/app.yaml` with the model serving endpoint name from Module 5 (`disa-cti-agent`) before deploying.

## 6. Compute sizing (for ~25 attendees)

| Resource | Size | Notes |
|---|---|---|
| Shared SQL warehouse | Small (4 DBU) | Serverless. Auto-stops after 10 min idle. |
| Model serving endpoint | Pay-per-token (Llama 4 Maverick + Claude Sonnet 4.6) | No provisioning needed. |
| Agent serving endpoint (`disa-cti-agent`) | Small (1 concurrency) | Scale to zero enabled. |

Total budget for a 3-hour workshop: ~30 DBUs across all attendees.

## 7. Cleanup after workshop

```bash
databricks bundle destroy -t dev
```

Or manually drop the catalog: `DROP CATALOG disa_workshop CASCADE;`
