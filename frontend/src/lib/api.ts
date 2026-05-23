"use client";

import { getToken } from "./auth";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ReportSummary {
  id: string;
  status: "pending" | "running" | "completed" | "failed";
  prompt: string;
  created_at: string;
}

export interface Report extends ReportSummary {
  result_md: string | null;
  extra: { subtasks?: string[]; paper_count?: number; papers?: Array<{ arxiv_id: string; title: string; pdf_url: string }> } | null;
  error: string | null;
  updated_at: string;
}

export interface ChatResponse {
  conversation_id: string;
  response: string;
  used_memories: number;
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init.headers as Record<string, string>) || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch {}
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  register: (email: string, password: string) =>
    request<{ id: string; email: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<{ id: string; email: string }>("/auth/me"),

  listResearch: () => request<ReportSummary[]>("/research"),

  createResearch: (prompt: string) =>
    request<Report>("/research", { method: "POST", body: JSON.stringify({ prompt }) }),

  getResearch: (id: string) => request<Report>(`/research/${id}`),

  streamResearchUrl: (id: string) => {
    const token = getToken();
    // EventSource doesn't allow custom headers — pass token as query param fallback?
    // Simpler: include via separate auth scheme. We'll just open without auth header.
    // The API requires auth, so we'd need to either:
    //  (a) move to fetch-based SSE reader, or
    //  (b) allow token via query param.
    // We use (a): the ProgressStream component reads via fetch.
    return { url: `${BASE}/research/${id}/stream`, token };
  },

  chat: (message: string, conversation_id?: string) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ message, conversation_id }),
    }),
};

export { ApiError };
