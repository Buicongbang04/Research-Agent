"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { use } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, ApiError, Report } from "@/lib/api";
import { getToken, isAuthed } from "@/lib/auth";

interface ProgressEvent {
  event: string;
  ts?: number;
  [k: string]: unknown;
}

const EVENT_LABELS: Record<string, string> = {
  snapshot: "Connected",
  planner_start: "🧠 Planner started",
  planner_done: "✅ Plan ready",
  search_start: "🔎 Search started",
  search_query_done: "📚 arXiv query done",
  search_query_failed: "⚠️ Query failed",
  search_done: "✅ Search complete",
  summarizer_start: "📝 Summarizing papers",
  summarizer_progress: "📝 Summarizing...",
  summarizer_done: "✅ Summaries ready",
  writer_start: "✍️ Writing report",
  writer_done: "🎉 Report complete",
  ping: "",
  done: "Done",
};

export default function ResearchDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [report, setReport] = useState<Report | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [streamError, setStreamError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!isAuthed()) {
      router.push("/login");
      return;
    }
    void loadReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (!report) return;
    if (report.status === "completed" || report.status === "failed") return;
    // Start SSE stream for in-progress reports
    abortRef.current = new AbortController();
    void streamProgress(abortRef.current.signal);
    return () => abortRef.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report?.status]);

  async function loadReport() {
    try {
      const r = await api.getResearch(id);
      setReport(r);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) router.push("/login");
    }
  }

  async function streamProgress(signal: AbortSignal) {
    const token = getToken();
    const url = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/research/${id}/stream`;
    try {
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
        signal,
      });
      if (!res.ok || !res.body) {
        setStreamError(`Stream HTTP ${res.status}`);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "message";

      while (!signal.aborted) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            try {
              const data = JSON.parse(line.slice(5).trim());
              if (currentEvent !== "ping") {
                setEvents((prev) => [...prev, { event: currentEvent, ...data }]);
              }
              if (currentEvent === "done" || currentEvent === "writer_done") {
                void loadReport();
                return;
              }
            } catch {}
          }
        }
      }
    } catch (err) {
      if (!signal.aborted) setStreamError(String(err));
    }
  }

  if (!report) {
    return <div className="text-slate-500">Loading…</div>;
  }

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg border shadow-sm">
        <h1 className="text-2xl font-bold mb-2">{report.prompt}</h1>
        <p className="text-sm text-slate-500">
          Status: <span className="font-semibold">{report.status}</span> · Created{" "}
          {new Date(report.created_at).toLocaleString()}
        </p>
        {report.error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-800">
            Error: {report.error}
          </div>
        )}
      </div>

      {(report.status === "pending" || report.status === "running") && (
        <div className="bg-white p-4 rounded-lg border shadow-sm">
          <h2 className="font-semibold mb-2 text-sm uppercase text-slate-600 tracking-wide">
            Progress
          </h2>
          {streamError && <p className="text-sm text-red-600">Stream error: {streamError}</p>}
          <ul className="space-y-1 text-sm font-mono">
            {events.map((e, i) => {
              const label = EVENT_LABELS[e.event] ?? e.event;
              if (!label) return null;
              return (
                <li key={i} className="flex gap-2">
                  <span className="text-slate-400 shrink-0">
                    {e.ts ? new Date(e.ts * 1000).toLocaleTimeString() : ""}
                  </span>
                  <span>{label}</span>
                  {"query" in e && <span className="text-slate-500">— {String(e.query)}</span>}
                  {"index" in e && "total" in e && (
                    <span className="text-slate-500">
                      ({String(e.index)}/{String(e.total)})
                    </span>
                  )}
                </li>
              );
            })}
            {events.length === 0 && <li className="text-slate-500">Waiting for events…</li>}
          </ul>
        </div>
      )}

      {report.result_md && (
        <article className="bg-white p-6 rounded-lg border shadow-sm prose prose-slate max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.result_md}</ReactMarkdown>
        </article>
      )}

      {report.extra?.papers && report.extra.papers.length > 0 && (
        <div className="bg-white p-4 rounded-lg border shadow-sm">
          <h3 className="font-semibold mb-2 text-sm uppercase text-slate-600 tracking-wide">
            Sources ({report.extra.papers.length})
          </h3>
          <ul className="space-y-1 text-sm">
            {report.extra.papers.map((p) => (
              <li key={p.arxiv_id}>
                <a
                  href={p.pdf_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-700 hover:underline"
                >
                  [{p.arxiv_id}] {p.title}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
