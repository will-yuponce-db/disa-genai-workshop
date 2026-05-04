# Vibe-Code Prompt: Genie SQL → Streamlit chart

A copy-paste prompt that turns any Genie-generated SQL query into a drop-in Streamlit snippet for the workshop app in `/app/app.py`. Use this during the live demo and take it home for your own apps.

## How to use

1. Ask a question in your Genie space.
2. Click **View SQL** in Genie. Copy the SQL query.
3. Click the **Result schema** tab (or look at the column headers + types). Copy them.
4. Paste both into the prompt below, fill in the chart goal, send to Claude.
5. Claude returns a Python snippet. Append it under the `Charts (vibe-code zone)` section in `app.py`.
6. Re-deploy by re-running notebook 06 (or running `databricks apps deploy` directly).

## The prompt

> Copy everything between the lines and paste into Claude (Sonnet 4.6 or newer recommended).

---

```
You are generating a Streamlit snippet for an existing Databricks App.

CONTEXT
- File: app/app.py (Streamlit, runs on Databricks Apps)
- The app already imports: streamlit as st, os, WorkspaceClient as w
- Available env vars: DATABRICKS_AGENT_ENDPOINT, DATABRICKS_CATALOG, DATABRICKS_SCHEMA, DATABRICKS_WAREHOUSE_ID
- Run SQL via: w.statement_execution.execute_statement(warehouse_id=..., statement=..., wait_timeout="30s")
  and read result.result.data_array (list of rows, each row a list of strings).
- Charting: prefer st.bar_chart / st.line_chart / st.dataframe; use plotly_chart for anything more custom.
- Styling: stick to Streamlit defaults; theme is cyber threat intel so favor red/amber/green for severity, blue for counts.

GENIE-GENERATED SQL
```sql
<paste the Genie SQL here>
```

RESULT SCHEMA
<paste the columns + types here, one per line, e.g.>
- vendor: STRING
- cve_count: BIGINT

GOAL
<one sentence describing the chart you want, e.g. "Top 10 KEV-listed vendors as a horizontal bar chart">

OUTPUT REQUIREMENTS
- A self-contained Python snippet (no new imports beyond what's already in app.py).
- Wrap in a `with st.expander("<title>", expanded=True):` block so it sits cleanly under the Charts section.
- Cache the SQL call with @st.cache_data(ttl=300) on a helper function.
- Handle the empty-result case with st.info(...).
- Cast numeric columns from string before charting (warehouse statement results come back as strings).
- No commentary or markdown around the code, just the Python.
```

---

## Worked example

**Goal:** Top 10 vendors by KEV catalog entry count.

**Genie SQL:**
```sql
SELECT vendorProject AS vendor, COUNT(*) AS cve_count
FROM <catalog>.<schema>.kev_catalog
GROUP BY vendorProject
ORDER BY cve_count DESC
LIMIT 10
```

**Schema:**
- vendor: STRING
- cve_count: BIGINT

**Claude returns** (paste under the vibe-code zone in `app.py`):

```python
@st.cache_data(ttl=300)
def _kev_top_vendors():
    res = w.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=f"""
            SELECT vendorProject AS vendor, COUNT(*) AS cve_count
            FROM {CATALOG}.{SCHEMA}.kev_catalog
            GROUP BY vendorProject
            ORDER BY cve_count DESC
            LIMIT 10
        """,
        wait_timeout="30s",
    )
    return [(r[0], int(r[1])) for r in (res.result.data_array or [])]

with st.expander("Top KEV vendors", expanded=True):
    rows = _kev_top_vendors()
    if not rows:
        st.info("No data yet — run notebook 00_setup first.")
    else:
        import pandas as pd
        df = pd.DataFrame(rows, columns=["vendor", "cve_count"]).set_index("vendor")
        st.bar_chart(df, horizontal=True)
```

Total time from question to running chart: about a minute.
