"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { isAuthed } from "@/lib/auth";

interface UIMessage {
  role: "user" | "assistant";
  content: string;
  memories?: number;
}

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isAuthed()) router.push("/login");
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || sending) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setSending(true);
    setError(null);
    try {
      const r = await api.chat(userMsg, conversationId);
      setConversationId(r.conversation_id);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: r.response, memories: r.used_memories },
      ]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Chat failed");
    } finally {
      setSending(false);
    }
  }

  function newConversation() {
    setConversationId(undefined);
    setMessages([]);
    setError(null);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Chat</h1>
        <button
          onClick={newConversation}
          className="text-sm px-3 py-1.5 border rounded-md hover:bg-slate-100"
        >
          + New conversation
        </button>
      </div>

      <div className="bg-white border rounded-lg shadow-sm min-h-[400px] max-h-[60vh] overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <p className="text-slate-500 text-sm">
            Start a conversation. Past messages are saved as long-term memory and recalled across
            conversations.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] px-4 py-2 rounded-lg whitespace-pre-wrap ${
                m.role === "user"
                  ? "bg-slate-900 text-white"
                  : "bg-slate-100 text-slate-900"
              }`}
            >
              {m.content}
              {m.role === "assistant" && typeof m.memories === "number" && m.memories > 0 && (
                <div className="text-xs mt-1 text-slate-500">
                  ↪ recalled {m.memories} memor{m.memories === 1 ? "y" : "ies"}
                </div>
              )}
            </div>
          </div>
        ))}
        {sending && (
          <div className="text-sm text-slate-500 italic">Assistant is thinking…</div>
        )}
        {error && <div className="text-sm text-red-600">{error}</div>}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={send} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          className="flex-1 px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-slate-500"
          disabled={sending}
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="bg-slate-900 text-white px-4 py-2 rounded-md hover:bg-slate-800 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
