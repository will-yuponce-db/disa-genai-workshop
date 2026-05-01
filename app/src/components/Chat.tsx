import { useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { sendMessage, type AgentResponse } from "../services/agent";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();

  async function handleSend() {
    const userText = input.trim();
    if (!userText) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: userText }]);
    setBusy(true);
    try {
      const uiContext = { path: location.pathname, searchParams: Object.fromEntries(searchParams) };
      const res: AgentResponse = await sendMessage(messages, userText, uiContext);
      setMessages((m) => [...m, { role: "assistant", content: res.assistantMessage }]);
      for (const action of res.actions || []) {
        if (action.type === "navigate") {
          const params = action.searchParams ? `?${new URLSearchParams(action.searchParams).toString()}` : "";
          navigate(action.path + params);
        } else if (action.type === "setSearchParams") {
          const next = new URLSearchParams(searchParams);
          for (const [k, v] of Object.entries(action.searchParams)) {
            if (v === null) next.delete(k);
            else next.set(k, v);
          }
          setSearchParams(next);
        }
      }
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: `Error: ${(e as Error).message}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-800 p-3 text-sm font-semibold">CTI Assistant</div>
      <div className="flex-1 overflow-auto p-3 space-y-3 text-sm">
        {messages.length === 0 && (
          <p className="text-slate-500 italic">Try: "Which KEV CVEs target Cisco IOS XE in our inventory?"</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`rounded p-2 ${m.role === "user" ? "bg-slate-800" : "bg-slate-900 border border-slate-800"}`}>
            <div className="text-xs text-slate-500 mb-1">{m.role}</div>
            <div className="whitespace-pre-wrap">{m.content}</div>
          </div>
        ))}
        {busy && <div className="text-slate-500 italic">thinking…</div>}
      </div>
      <div className="border-t border-slate-800 p-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask about CVEs, STIGs, assets…"
          className="flex-1 rounded bg-slate-950 border border-slate-700 px-3 py-2 text-sm"
          disabled={busy}
        />
        <button
          onClick={handleSend}
          disabled={busy}
          className="rounded bg-blue-600 hover:bg-blue-500 px-3 py-2 text-sm disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
