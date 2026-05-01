#!/usr/bin/env python3
"""Workshop-specific data setup, called from workspace_init.py.

Uploads the CISA advisory PDFs and STIG XCCDF files to UC volumes, and creates
seed Delta tables (cves, kev_catalog, stig_findings, affected_assets) from
JSON snapshots bundled in /voc/private/courseware/disa_workshop_data/.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CATALOG = "disa_workshop"
SCHEMA = "threat_intel"
ADVISORY_VOLUME = "raw_advisories"
STIG_VOLUME = "raw_stigs"


def _exec(warehouse_client, statement: str) -> None:
    print(f"  SQL: {statement[:80]}{'...' if len(statement) > 80 else ''}")
    warehouse_client.execute_statement(statement=statement, wait_timeout="30s")


def setup_workshop_data(workspace_client, warehouse_id: str, data_dir: str) -> None:
    print(f"Setting up workshop data from {data_dir}")

    sql = workspace_client.statement_execution
    base = f"{CATALOG}.{SCHEMA}"

    for stmt in [
        f"CREATE CATALOG IF NOT EXISTS {CATALOG}",
        f"CREATE SCHEMA IF NOT EXISTS {base}",
        f"CREATE VOLUME IF NOT EXISTS {base}.{ADVISORY_VOLUME}",
        f"CREATE VOLUME IF NOT EXISTS {base}.{STIG_VOLUME}",
    ]:
        sql.execute_statement(
            statement=stmt, warehouse_id=warehouse_id, wait_timeout="30s"
        )

    advisory_dir = Path(data_dir) / "advisories"
    if advisory_dir.exists():
        for pdf in advisory_dir.glob("*.pdf"):
            target = f"/Volumes/{CATALOG}/{SCHEMA}/{ADVISORY_VOLUME}/{pdf.name}"
            with pdf.open("rb") as f:
                workspace_client.files.upload(file_path=target, contents=f, overwrite=True)
            print(f"  Uploaded {pdf.name}")

    stig_dir = Path(data_dir) / "stigs"
    if stig_dir.exists():
        for xml in stig_dir.glob("*.xml"):
            target = f"/Volumes/{CATALOG}/{SCHEMA}/{STIG_VOLUME}/{xml.name}"
            with xml.open("rb") as f:
                workspace_client.files.upload(file_path=target, contents=f, overwrite=True)
            print(f"  Uploaded {xml.name}")

    seed_sql_dir = Path(data_dir) / "seed_sql"
    if seed_sql_dir.exists():
        for sql_file in sorted(seed_sql_dir.glob("*.sql")):
            with sql_file.open() as f:
                statements = [s.strip() for s in f.read().split(";") if s.strip()]
            for stmt in statements:
                sql.execute_statement(
                    statement=stmt, warehouse_id=warehouse_id, wait_timeout="60s"
                )
            print(f"  Ran {sql_file.name} ({len(statements)} statements)")

    sql.execute_statement(
        statement=f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `account users`",
        warehouse_id=warehouse_id,
        wait_timeout="30s",
    )
    sql.execute_statement(
        statement=f"GRANT USE SCHEMA, SELECT, READ VOLUME ON SCHEMA {base} TO `account users`",
        warehouse_id=warehouse_id,
        wait_timeout="30s",
    )

    print("Workshop data setup complete.")
