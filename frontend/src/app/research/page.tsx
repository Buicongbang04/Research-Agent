"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError, ReportSummary } from "@/lib/api";
import { isAuthed } from "@/lib/auth";

const STATUS_CLASS: Record<string, string> = {
  pending: "bg-slate-200 text-slate-700",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export default function ResearchPage() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthed()) {
      router.push("/login");
      return;
    }
    void load();
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function load() {
    try {
      const data = await api.listResearch();
      setReports(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/login");
      }
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!prompt.trim()) return;
    setError(null);
    setSubmitting(true);
    try {
      const r = await api.createResearch(prompt);
      setPrompt("");
      router.push(`/research/${r.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to submit");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="bg-white p-6 rounded-lg border shadow-sm">
        <h1 className="text-2xl font-bold mb-3">New research</h1>
        <form onSubmit={onSubmit} className="space-y-3">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe what you want to research, e.g. 'Recent advances in retrieval augmented generation'"
            className="w-full px-3 py-2 border rounded-md min-h-[80px] focus:outline-none focus:ring-2 focus:ring-slate-500"
            required
            minLength={4}
            maxLength={2000}
          />
          {error && <div className="text-sm text-red-600">{error}</div>}
          <button
            type="submit"
            disabled={submitting}
            className="bg-slate-900 text-white px-4 py-2 rounded-md hover:bg-slate-800 disabled:opacity-50"
          >
            {submitting ? "Submitting..." : "Start research"}
          </button>
        </form>
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-3">Your reports</h2>
        {reports.length === 0 ? (
          <p className="text-slate-500 text-sm">No reports yet — submit your first research above.</p>
        ) : (
          <ul className="space-y-2">
            {reports.map((r) => (
              <li key={r.id}>
                <Link
                  href={`/research/${r.id}`}
                  className="block bg-white p-4 rounded-lg border hover:border-slate-400 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <p className="font-medium line-clamp-2">{r.prompt}</p>
                      <p className="text-xs text-slate-500 mt-1">
                        {new Date(r.created_at).toLocaleString()}
                      </p>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_CLASS[r.status]}`}
                    >
                      {r.status}
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
