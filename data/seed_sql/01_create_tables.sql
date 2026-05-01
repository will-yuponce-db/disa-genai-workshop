-- Optional seed SQL run by vocareum/scripts/python/workshop_data_setup.py.
-- The bulk of seed data is loaded by notebooks/00_setup.ipynb directly via Spark.
-- Add edge-case fixtures here.

CREATE TABLE IF NOT EXISTS disa_workshop.threat_intel.cves (
  cve_id STRING,
  description STRING,
  published_date DATE,
  cvss_score DOUBLE,
  cvss_severity STRING,
  attack_vector STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS disa_workshop.threat_intel.affected_assets (
  asset_id STRING,
  hostname STRING,
  environment STRING,
  vendor STRING,
  product STRING,
  os_family STRING,
  last_patched DATE,
  owner_org STRING
) USING DELTA;
