#!/bin/bash
#
# upload.sh -- Build notebook archive and upload Vocareum lab files via REST API v2
#
# Usage:
#   export VOC_TOKEN="your-personal-access-token"
#   export VOC_COURSE_ID="your-course-id"
#   export VOC_ASSIGNMENT_ID="your-assignment-id"
#   export VOC_PART_ID="your-part-id"
#   ./upload.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_BASE="https://api.vocareum.com/api/v2"

for var in VOC_TOKEN VOC_COURSE_ID VOC_ASSIGNMENT_ID VOC_PART_ID; do
    if [[ -z "${!var:-}" ]]; then
        echo "ERROR: $var is not set" >&2
        exit 1
    fi
done

ENDPOINT="${API_BASE}/courses/${VOC_COURSE_ID}/assignments/${VOC_ASSIGNMENT_ID}/parts/${VOC_PART_ID}"

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# --- Build notebook archive ---
echo "Building notebook archive..."
NOTEBOOK_ZIP="$TMPDIR/disa-genai-workshop.zip"
(cd "$REPO_ROOT" && zip -r "$NOTEBOOK_ZIP" \
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
    -x '*.DS_Store' > /dev/null)
echo "  Built: $(du -h "$NOTEBOOK_ZIP" | cut -f1)"

# --- Build data archive (advisories + stigs + seed SQL) ---
echo "Building data archive..."
DATA_ZIP="$TMPDIR/disa_workshop_data.zip"
(cd "$REPO_ROOT" && zip -r "$DATA_ZIP" data/ -x '*.DS_Store' > /dev/null)
echo "  Built: $(du -h "$DATA_ZIP" | cut -f1)"

upload_target() {
    local target="$1"
    local src_dir="$2"

    if [[ ! -d "$src_dir" ]]; then
        echo "  SKIP $target (no files)"
        return
    fi

    local zip_path="$TMPDIR/${target}.zip"
    (cd "$src_dir" && zip -r "$zip_path" . -x '*.DS_Store' > /dev/null)

    local zip_b64
    zip_b64=$(base64 < "$zip_path")
    local payload_path="$TMPDIR/${target}_payload.json"

    python3 -c "
import json, sys
b64 = sys.stdin.read()
with open('$payload_path', 'w') as f:
    json.dump({
        'update': 1,
        'content': [
            {'target': '$target', 'zipcontent': b64}
        ]
    }, f)
" <<< "$zip_b64"

    local http_code
    http_code=$(curl -s -o "$TMPDIR/${target}_response.json" -w "%{http_code}" \
        -X PUT "$ENDPOINT" \
        -H "Authorization: Token $VOC_TOKEN" \
        -H "Content-Type: application/json" \
        -d @"$payload_path")

    local size
    size=$(du -h "$zip_path" | cut -f1)

    if [[ "$http_code" == "200" || "$http_code" == "202" ]]; then
        echo "  OK   $target ($size)"
    else
        echo "  FAIL $target -- HTTP $http_code"
        cat "$TMPDIR/${target}_response.json" 2>/dev/null
        echo ""
        return 1
    fi
}

# --- Stage upload packages ---
echo "Staging upload packages..."

PRIVATE_DIR="$TMPDIR/stage_private"
mkdir -p "$PRIVATE_DIR/courseware"
cp "$SCRIPT_DIR/courseware/disa-workshop.cfg" "$PRIVATE_DIR/courseware/"
cp "$NOTEBOOK_ZIP"                            "$PRIVATE_DIR/courseware/disa-genai-workshop.zip"
cp "$DATA_ZIP"                                "$PRIVATE_DIR/courseware/disa_workshop_data.dat"

SCRIPTS_DIR="$TMPDIR/stage_scripts"
mkdir -p "$SCRIPTS_DIR/python"
cp "$SCRIPT_DIR/scripts/"*.sh             "$SCRIPTS_DIR/"
cp "$SCRIPT_DIR/scripts/python/"*.py      "$SCRIPTS_DIR/python/"

DOCS_DIR="$TMPDIR/stage_docs"
mkdir -p "$DOCS_DIR"
cp "$REPO_ROOT/README.md" "$DOCS_DIR/"

# --- Upload ---
echo ""
echo "Uploading to Vocareum (update=1, overwrites existing)..."
echo "  Course:     $VOC_COURSE_ID"
echo "  Assignment: $VOC_ASSIGNMENT_ID"
echo "  Part:       $VOC_PART_ID"
echo ""

FAILED=0
upload_target "private" "$PRIVATE_DIR" || FAILED=1
sleep 15
upload_target "scripts" "$SCRIPTS_DIR" || FAILED=1
sleep 15
upload_target "docs" "$DOCS_DIR" || FAILED=1

echo ""
if [[ "$FAILED" -eq 0 ]]; then
    echo "All uploads successful."
else
    echo "Some uploads failed. Check output above." >&2
    exit 1
fi
