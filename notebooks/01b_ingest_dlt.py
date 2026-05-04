# Databricks Lakeflow Declarative Pipeline (formerly Delta Live Tables) source.
#
# This file is the *pipeline definition*. It is NOT a regular notebook — it must
# be attached to a pipeline (created by `01b_create_dlt_pipeline.ipynb`) and run
# via the Pipelines UI or the Pipelines API. Opening it in the workspace will
# show the DLT graph editor.
#
# Pipeline parameters (set in the pipeline config — see 01b_create_dlt_pipeline):
#   workshop.catalog  -> e.g. main
#   workshop.schema   -> e.g. cti_<user>
#
# The pipeline target catalog/schema is also set via the `catalog` and `target`
# pipeline fields, so DLT writes the bronze/silver/gold tables straight into
# the per-user schema.

import dlt
from pyspark.sql import functions as F

CATALOG = spark.conf.get("workshop.catalog")
SCHEMA = spark.conf.get("workshop.schema")
ADVISORY_VOLUME = f"/Volumes/{CATALOG}/{SCHEMA}/raw_advisories"


# ---------- BRONZE: raw PDF binaries ingested from the UC volume ----------

@dlt.table(
    name="bronze_advisory_files",
    comment="Raw PDF binaries from the CISA advisories volume. Auto Loader picks up new files on each pipeline run.",
)
def bronze_advisory_files():
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "binaryFile")
        .option("cloudFiles.includeExistingFiles", "true")
        .load(ADVISORY_VOLUME)
        .withColumn("ingested_at", F.current_timestamp())
    )


# ---------- SILVER: ai_parse_document over the bronze PDFs ----------

@dlt.table(
    name="silver_parsed_advisories",
    comment="ai_parse_document output for each advisory PDF. The `parsed` column holds the structured document graph.",
)
@dlt.expect_or_drop("has_parsed", "parsed IS NOT NULL")
def silver_parsed_advisories():
    src = dlt.read_stream("bronze_advisory_files")
    return src.selectExpr(
        "path",
        "modificationTime",
        "ingested_at",
        "ai_parse_document(content) AS parsed",
    )


# ---------- GOLD: structured threat-intel extraction via ai_query ----------

EXTRACT_SCHEMA = """{
  "type": "json_schema",
  "json_schema": {
    "name": "advisory_extract",
    "schema": {
      "type": "object",
      "properties": {
        "title":       {"type": "string"},
        "summary":     {"type": "string"},
        "cves":        {"type": "array", "items": {"type": "string"}},
        "vendors":     {"type": "array", "items": {"type": "string"}},
        "products":    {"type": "array", "items": {"type": "string"}},
        "mitigations": {"type": "array", "items": {"type": "string"}}
      },
      "required": ["title", "summary", "cves"]
    },
    "strict": true
  }
}""".replace("'", "''")


@dlt.table(
    name="gold_advisories",
    comment="Structured CVE / vendor / product / mitigation extract per advisory. Joinable with kev_catalog on cve_id.",
)
def gold_advisories():
    src = dlt.read("silver_parsed_advisories")
    extracted = src.selectExpr(
        "path",
        f"""ai_query(
            'databricks-claude-haiku-4-5',
            CONCAT(
              'Extract structured threat intelligence from this CISA advisory. Return JSON only.\\n\\n',
              LEFT(CAST(parsed AS STRING), 8000)
            ),
            responseFormat => '{EXTRACT_SCHEMA}'
        ) AS extract""",
    )
    return extracted.selectExpr(
        "path",
        "parse_json(extract):title::string AS title",
        "parse_json(extract):summary::string AS summary",
        "from_json(parse_json(extract):cves::string, 'ARRAY<STRING>') AS cves",
        "from_json(parse_json(extract):vendors::string, 'ARRAY<STRING>') AS vendors",
        "from_json(parse_json(extract):products::string, 'ARRAY<STRING>') AS products",
        "from_json(parse_json(extract):mitigations::string, 'ARRAY<STRING>') AS mitigations",
    )


# ---------- GOLD: advisories joined to KEV catalog (active-exploitation flag) ----------

@dlt.table(
    name="gold_advisory_kev_matches",
    comment="Per-advisory CVEs matched against the CISA KEV catalog. One row per (advisory, CVE) where the CVE is in KEV.",
)
def gold_advisory_kev_matches():
    g = dlt.read("gold_advisories").selectExpr(
        "path", "title", "explode(cves) AS cve"
    )
    kev = spark.read.table(f"{CATALOG}.{SCHEMA}.kev_catalog")
    return (
        g.alias("a")
        .join(kev.alias("k"), F.col("a.cve") == F.col("k.cveID"))
        .selectExpr(
            "a.path",
            "a.title",
            "a.cve",
            "k.dateAdded AS kev_date_added",
            "k.dueDate   AS kev_due_date",
            "k.requiredAction AS kev_required_action",
            "k.knownRansomwareCampaignUse AS ransomware_use",
        )
    )
