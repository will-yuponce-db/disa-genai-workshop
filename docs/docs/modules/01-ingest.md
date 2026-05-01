# Module 1 — Document Ingest with `ai_parse_document` + `ai_query`

**Time**: 30 minutes

## What you'll do

Starting from a folder of CISA advisory PDFs in a Unity Catalog volume, end with a structured Delta table of CVEs, affected products, and recommended mitigations. Two SQL calls.

## Why this matters for DISA

This is what a CSSP analyst does manually today: open a PDF, copy CVE IDs into a spreadsheet, link them to the asset inventory. We're collapsing that into a SQL query that runs in seconds across the whole advisory corpus.

## Pipeline

```
raw PDFs in volume
   ↓ ai_parse_document (OCR + layout-aware extraction)
parsed_advisories
   ↓ ai_query with structured output schema
structured_advisories
   ↓ JSON flatten
advisories (view: title, cves, vendors, products, mitigations)
   ↓ JOIN with kev_catalog
high-priority advisories citing actively-exploited CVEs
```

## Key SQL

```sql
-- Parse PDFs in the volume
CREATE OR REPLACE TABLE disa_workshop.threat_intel.parsed_advisories AS
SELECT path, ai_parse_document(content) AS parsed
FROM READ_FILES('/Volumes/disa_workshop/threat_intel/raw_advisories', format => 'binaryFile');

-- Extract structured fields
CREATE OR REPLACE TABLE disa_workshop.threat_intel.structured_advisories AS
SELECT
  path,
  ai_query(
    'databricks-meta-llama-3-3-70b-instruct',
    CONCAT('Extract structured threat intel from this advisory ...', LEFT(parsed.document.pages[0].content, 8000)),
    responseFormat => '{...}'
  ) AS extract
FROM disa_workshop.threat_intel.parsed_advisories;
```

## Try it yourself

1. Modify the schema to add a `severity_assessment` field.
2. Swap `databricks-meta-llama-3-3-70b-instruct` for `databricks-claude-sonnet-4-6` and compare.
3. Use `ai_summarize` to produce a 2-sentence daily-brief across all advisories.

[Open the notebook →](https://github.com/your-handle/disa-genai-workshop/blob/main/notebooks/01_ingest_advisories.ipynb)
