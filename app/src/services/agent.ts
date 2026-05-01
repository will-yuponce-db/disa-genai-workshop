interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AgentAction {
  type: "navigate" | "setSearchParams" | "highlightCves";
  path?: string;
  searchParams?: Record<string, string | null>;
  cveIds?: string[];
}

export interface AgentResponse {
  assistantMessage: string;
  actions: AgentAction[];
}

const ALLOWED_PATHS = new Set(["/", "/threats", "/charts"]);

export async function sendMessage(
  history: ChatMessage[],
  userMessage: string,
  uiContext: Record<string, unknown>
): Promise<AgentResponse> {
  const r = await fetch("/api/agent/step", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ history, userMessage, uiContext }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const raw = await r.json();
  const content = raw.choices?.[0]?.message?.content || raw.assistantMessage || "";
  let parsed: AgentResponse;
  try {
    parsed = typeof content === "string" ? JSON.parse(content) : content;
  } catch {
    return { assistantMessage: typeof content === "string" ? content : JSON.stringify(content), actions: [] };
  }
  parsed.actions = (parsed.actions || []).filter((a) => {
    if (a.type === "navigate") return a.path && ALLOWED_PATHS.has(a.path);
    return true;
  });
  return parsed;
}
