# Module 4 — Knowledge Assistant (Agent Bricks)

**Time**: 20 minutes

## What you'll build

A no-code RAG agent over CISA advisories, DoD STIG XCCDF excerpts, and MITRE ATT&CK technique pages.

`notebooks/04_knowledge_assistant.ipynb` creates the Knowledge Assistant programmatically via **`POST /api/2.1/knowledge-assistants`**. The endpoint name (`ka-<id>-endpoint`) is persisted to `_workshop_config` so Module 5's compound agent picks it up automatically.

## Why we picked KA over a knowledge graph

A knowledge graph is the right answer for relationship-heavy queries (*"who is connected to whom"*). For DISA's primary need — *"what does this STIG control require"*, *"what does CISA recommend for this CVE"* — a vector-based KA over authoritative documents is faster to set up and easier to maintain. We dropped the KG to keep the workshop in 2.5 hours.

## What the notebook does

1. Stages the corpus at `/Volumes/main/cti_<user>/ka_corpus`:
   - All advisory PDFs from `raw_advisories/`
   - All STIG snippet text files from `raw_stigs/`
   - The first 50 ATT&CK techniques as `attack_<id>.txt`
2. POSTs `/api/2.1/knowledge-assistants` with display name `disa-cti-knowledge`, description, and instructions.
3. POSTs `/api/2.1/knowledge-assistants/<id>/knowledge-sources` with `source_type: FILES` pointing at the volume.
4. Persists `ka_id` and `ka_endpoint` into `_workshop_config`.

The notebook is idempotent: re-running it reuses an existing KA by display name and skips re-attaching the corpus if it's already attached.

## Important: warm-up time

The KA endpoint takes **10-20 minutes** to provision the first time. The notebook does not block on this. Module 5's compound agent has a graceful fallback: if the KA endpoint is not yet `ONLINE`, the agent returns a polite "knowledge assistant not yet ready" message and continues using its other tools.

## What the notebook leaves to the UI

Nothing required. Optional enrichments via the Agent Bricks UI:

- **Sidebar → Agents → Knowledge Assistants → disa-cti-knowledge** to:
  - Watch indexing progress.
  - Test queries inline.
  - Add additional knowledge sources (other volumes, web pages, Confluence, etc.).
  - Review natural-language feedback from subject matter experts.

## System prompt

The notebook applies the following instructions on creation:

```text
You are a DISA cyber threat intelligence assistant. Answer questions about CISA advisories,
DoD STIGs, and MITRE ATT&CK techniques. Always cite the source document name and section.

If the answer is not in the retrieved context, say so explicitly. Do not make up CVE IDs,
STIG identifiers, or ATT&CK technique IDs.

When citing a STIG control, include both the STIG-ID (e.g., V-220701) and the severity (CAT I/II/III).
When citing an ATT&CK technique, include the technique ID (e.g., T1059.001).
```

## Test questions (run after the endpoint warms up)

1. What does CISA recommend for ransomware on legacy Windows?
2. Which STIG controls cover privileged account auditing on Windows Server?
3. Summarize the most recent advisory and list its CVEs.
4. What ATT&CK technique covers PowerShell-based execution?
5. Are there advisories specifically calling out Cisco IOS XE?

[Open the notebook →](https://github.com/will-yuponce-db/disa-genai-workshop/blob/main/notebooks/04_knowledge_assistant.ipynb)
