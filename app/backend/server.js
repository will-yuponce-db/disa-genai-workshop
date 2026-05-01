import express from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";
import createApp from "./createApp.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.PORT || 8000;

const app = createApp();

const distDir = path.resolve(__dirname, "..", "dist");
app.use(express.static(distDir));
app.get("*", (_req, res) => res.sendFile(path.join(distDir, "index.html")));

app.listen(PORT, () => {
  console.log(`[server] listening on :${PORT}`);
});
