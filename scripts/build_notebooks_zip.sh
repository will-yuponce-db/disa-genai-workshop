#!/bin/bash
# Build a fallback zip of all workshop notebooks. Mirrors the zip auto-imported
# by the Vocareum lab; commit the output so attendees can download it directly
# if Vocareum auto-import isn't working.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="dist/disa-genai-workshop-notebooks.zip"
rm -f "$OUT"
zip -r "$OUT" \
  notebooks/_config.ipynb \
  notebooks/00_setup.ipynb \
  notebooks/01_ingest_advisories.ipynb \
  notebooks/01b_create_dlt_pipeline.ipynb \
  notebooks/01b_ingest_dlt.py \
  notebooks/02_ai_playground.ipynb \
  notebooks/03_netops_ai_query.ipynb \
  notebooks/04_genie_setup.ipynb \
  notebooks/05_knowledge_assistant.ipynb \
  notebooks/06_compound_agent.ipynb \
  notebooks/07_ai_query_agent.ipynb \
  notebooks/08_deploy_app.ipynb \
  -x '*.DS_Store' >/dev/null
ls -la "$OUT"
unzip -l "$OUT"
