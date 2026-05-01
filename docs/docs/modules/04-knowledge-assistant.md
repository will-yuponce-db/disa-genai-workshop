# Module 4 — Knowledge Assistant (Agent Bricks)

**Time**: 20 minutes

## What you'll build

A no-code RAG agent over CISA advisories, DoD STIG XCCDF excerpts, and MITRE ATT&CK technique pages.

## Why we picked KA over a knowledge graph

A knowledge graph is the right answer for relationship-heavy queries (*"who is connected to whom"*). For DISA's primary need — *"what does this STIG control require"*, *"what does CISA recommend for this CVE"* — a vector-based KA over authoritative documents is faster to set up and easier to maintain. We dropped the KG to keep the workshop in 2.5 hours.

## Setup steps

1. Stage the corpus at `/Volumes/disa_workshop/threat_intel/ka_corpus` (advisories + STIGs + ATT&CK technique snippets).
2. Workspace UI → **Agents > Knowledge Assistant > Create**:
   - Name: `disa-cti-knowledge`
   - Source: that volume
   - Embedding: `databricks-gte-large-en`
   - System prompt: see notebook
3. Wait ~3 min for the index build.
4. Test with five questions that exercise each document type.

## Test questions

1. What does CISA recommend for ransomware on legacy Windows?
2. Which STIG controls cover privileged account auditing on Windows Server?
3. Summarize the most recent advisory and list its CVEs.
4. What ATT&CK technique covers PowerShell-based execution?
5. Are there advisories specifically calling out Cisco IOS XE?

[Open the notebook →](https://github.com/your-handle/disa-genai-workshop/blob/main/notebooks/04_knowledge_assistant.ipynb)
