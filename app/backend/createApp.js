import express from "express";
import { DBSQLClient } from "@databricks/sql";
import fetch from "node-fetch";
import { buildSystemPrompt } from "./agent/prompt.js";

const MAX_ACTIONS = parseInt(process.env.DATABRICKS_AGENT_MAX_ACTIONS || "5", 10);

const SQL_ALLOWLIST = [
  /^select\s/i,
  /^with\s/i,
];

function isReadOnlySql(sql) {
  const trimmed = sql.trim();
  if (!SQL_ALLOWLIST.some((re) => re.test(trimmed))) return false;
  return !/(insert|update|delete|drop|create|alter|grant|revoke|truncate)\s/i.test(trimmed);
}

async function runSql(sql) {
  const client = new DBSQLClient();
  await client.connect({
    host: (process.env.DATABRICKS_HOST || "").replace(/^https?:\/\//, ""),
    path: process.env.DATABRICKS_HTTP_PATH,
    token: process.env.DATABRICKS_TOKEN,
  });
  const session = await client.openSession();
  try {
    const op = await session.executeStatement(sql, { runAsync: true, maxRows: 1000 });
    const rows = await op.fetchAll();
    const schema = (await op.getSchema()).map((c) => ({ name: c.columnName, type: c.typeDesc.types[0].primitiveEntry.type }));
    await op.close();
    return { rows, schema };
  } finally {
    await session.close();
    await client.close();
  }
}

async function callAgent(messages) {
  const host = process.env.DATABRICKS_HOST?.replace(/\/$/, "");
  const endpoint = process.env.DATABRICKS_AGENT_ENDPOINT;
  const url = `${host}/serving-endpoints/${endpoint}/invocations`;
  const r = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.DATABRICKS_TOKEN}`,
    },
    body: JSON.stringify({ messages }),
  });
  if (!r.ok) throw new Error(`Agent call failed: ${r.status} ${await r.text()}`);
  return r.json();
}

export default function createApp() {
  const app = express();
  app.use(express.json({ limit: "1mb" }));

  app.get("/api/health", (_req, res) => res.json({ ok: true }));

  app.post("/api/sql", async (req, res) => {
    const sql = (req.body?.sql || "").trim();
    if (!sql) return res.status(400).json({ error: "sql required" });
    if (!isReadOnlySql(sql)) return res.status(400).json({ error: "only read-only SELECT/WITH allowed" });
    try {
      const result = await runSql(sql);
      res.json(result);
    } catch (e) {
      res.status(500).json({ error: String(e.message || e) });
    }
  });

  app.post("/api/agent/step", async (req, res) => {
    const { history = [], userMessage = "", uiContext = {} } = req.body || {};
    const system = buildSystemPrompt({ maxActions: MAX_ACTIONS });
    const messages = [
      { role: "system", content: system },
      ...history,
      { role: "user", content: `APP_CONTEXT_JSON: ${JSON.stringify(uiContext)}\n\n${userMessage}` },
    ];
    try {
      const out = await callAgent(messages);
      res.json(out);
    } catch (e) {
      res.status(500).json({ error: String(e.message || e) });
    }
  });

  return app;
}
