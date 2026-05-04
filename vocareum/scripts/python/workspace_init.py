#!/usr/bin/env python3
"""Vocareum workspace_init.py — runs once when the workspace is first provisioned.

Sets up:
1. Metastore, default catalog, shared warehouse (via dbacademy)
2. CISA / NVD / MITRE ATT&CK / STIG seed data uploaded to UC volumes
3. Delta tables for Genie (cves, kev_catalog, stig_findings, affected_assets)
4. Permissions for all attendees
"""
import os
import sys
import zipfile


sys.path.insert(0, os.path.dirname(__file__))

import _dbacademy_vs_patch  # noqa: F401  applies SDK name-sanitization

sys.path.insert(0, "/voc/scripts/python")
from dbacademy import voc_init

print("=" * 60)
print("WORKSPACE INIT: DISA GenAI Workshop")
print("=" * 60)


db = voc_init()
db.workspace_init()

print("=" * 60)
print("PHASE 2: Workshop-specific data setup")
print("=" * 60)

data_zips = [
    "/voc/private/courseware/disa_workshop_data.dat",
    "/voc/private/courseware/disa_workshop_data.zip",
]
candidate_dirs = [
    "/voc/private/courseware/disa_workshop_data",
    "/voc/private/courseware",
]
data_dir = None

for d in candidate_dirs:
    if os.path.exists(d):
        contents = os.listdir(d)
        if any(f.endswith(".pdf") for f in contents) or any(f.endswith(".json") for f in contents):
            data_dir = d
            print(f"Found seed data at {data_dir}")
            break

if data_dir is None:
    for data_zip in data_zips:
        if os.path.exists(data_zip):
            print(f"Extracting {data_zip}...")
            with zipfile.ZipFile(data_zip, "r") as z:
                z.extractall("/voc/private/courseware/")
            data_dir = "/voc/private/courseware/disa_workshop_data"
            print(f"Extracted to {data_dir}")
            break

if data_dir is None:
    print("WARNING: No seed data found. Attendees will need to download via notebook 00_setup.ipynb.")
    sys.exit(0)

from workshop_data_setup import setup_workshop_data

setup_workshop_data(
    workspace_client=db.w,
    warehouse_id=db._warehouse,
    data_dir=data_dir,
)

print("=" * 60)
print("WORKSPACE INIT COMPLETE")
print("=" * 60)
