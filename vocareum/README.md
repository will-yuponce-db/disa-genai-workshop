# Vocareum Integration

This directory packages the workshop for the Vocareum lab platform. It mirrors the structure of `databricks-neo4j-lab/vocareum/` so existing admin muscle memory carries over.

## Layout

```
vocareum/
├── courseware/
│   └── disa-workshop.cfg     # Vocareum content + cluster config
├── scripts/
│   ├── workspace_init.sh     # Lifecycle: provisions catalog, schema, volumes, seed data
│   ├── user_setup.sh         # Lifecycle: per-attendee first-time setup
│   ├── lab_setup.sh          # Lifecycle: resume on lab re-entry
│   ├── lab_end.sh            # Lifecycle: pause warehouse on lab exit
│   └── python/
│       ├── workspace_init.py
│       ├── user_setup.py
│       ├── lab_setup.py
│       ├── lab_end.py
│       └── workshop_data_setup.py
├── upload.sh                 # Bundles + uploads to Vocareum REST API v2
└── README.md
```

## Lifecycle

1. **Workspace init** (admin runs once): provisions UC catalog `disa_workshop`, schema `threat_intel`, volumes, and seed Delta tables.
2. **User setup** (runs first time an attendee opens the lab): creates the attendee's Databricks user, mounts notebooks under `/Workspace/Users/<email>/`.
3. **Lab setup** (runs on every lab re-entry): resumes the attendee's serverless warehouse, returns redirect URL.
4. **Lab end** (runs on session timeout / explicit end): pauses warehouse to control cost.

## Upload

```bash
export VOC_TOKEN="..."
export VOC_COURSE_ID="..."
export VOC_ASSIGNMENT_ID="..."
export VOC_PART_ID="..."

./upload.sh
```

## Compute model

Attendees share a single workspace (~25 attendees per workspace). Each gets their own UC schema-scoped permissions; data tables are read-only shared. Compute is serverless throughout (SQL warehouse + Model Serving) so there is no cluster spinup wait.
