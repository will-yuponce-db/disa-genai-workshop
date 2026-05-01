# Workshop data

Sample data committed for offline / Vocareum demos. Most data is downloaded live from public APIs in `notebooks/00_setup.ipynb`; this directory only holds files that need to be hand-curated or are too slow to download on demand.

## Layout

```
data/
├── advisories/   # ~20 sample CISA advisory PDFs (committed)
├── stigs/        # ~50 sample STIG XCCDF excerpts (committed)
└── seed_sql/     # SQL scripts to populate edge-case tables
```

## How to refresh

### Advisories

```bash
# Pull the latest 20 advisories from cisa.gov
mkdir -p data/advisories
# (Download links come from https://www.cisa.gov/news-events/cybersecurity-advisories)
# Save PDF files into data/advisories/
```

### STIGs

```bash
# Download from https://public.cyber.mil/stigs/downloads/
# Extract a few XCCDF XML files (Windows, Linux, Cisco IOS) into data/stigs/
```

## Licensing

All files here are public-domain US Government works (CISA, DoD), reproducible from the public sources above. No PII or classified content.
