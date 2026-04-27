/**
 * Ekklesia.gr API Client
 * Kommuniziert mit FastAPI Backend (apps/api)
 * Copyright (c) 2026 Vendetta Labs — MIT License
 */
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.ekklesia.gr";

export const api = axios.create({
  baseURL: API_URL,
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
});

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Statement {
  id: number;
  text_el: string;
  text_en: string | null;
  explanation_el: string | null;
  explanation_en: string | null;
  category: string | null;
  display_order: number;
}

export interface Party {
  id: number;
  name_el: string;
  name_en: string | null;
  abbreviation: string | null;
  color_hex: string | null;
  description_el: string | null;
}

export interface PartyMatchResult {
  party_id: number;
  name_el: string;
  name_en: string | null;
  abbreviation: string | null;
  color_hex: string | null;
  match_percent: number;
  answered_count: number;
}

export interface Bill {
  id: string;
  title_el: string;
  title_en: string | null;
  pill_el: string | null;
  pill_en: string | null;
  summary_short_el: string | null;
  summary_short_en: string | null;
  summary_long_el: string | null;
  summary_long_en: string | null;
  categories: string[] | null;
  party_votes_parliament: Record<string, string> | null;
  status: string;
  parliament_vote_date: string | null;
  ai_summary_reviewed?: boolean;
  relevance_score?: number;
  forum_topic_id?: number | null;
}

export interface DivergenceResult {
  score: number;
  label_el: string;
  citizen_majority: string;
  parliament_result: string | null;
  headline_el: string;
}

export interface BillResults {
  bill_id: string;
  title_el: string;
  status: string;
  total_votes: number;
  yes_count: number;
  no_count: number;
  abstain_count: number;
  yes_percent: number;
  no_percent: number;
  abstain_percent: number;
  divergence: DivergenceResult | null;
  disclaimer_el: string;
}

// ─── API Calls ────────────────────────────────────────────────────────────────

export const ekklesia = {
  // VAA
  getStatements: () => api.get<Statement[]>("/api/v1/vaa/statements"),
  getParties:    () => api.get<Party[]>("/api/v1/vaa/parties"),
  match: (answers: Record<number, number>) =>
    api.post("/api/v1/vaa/match", { answers }),

  // Parliament
  getBills:    (status?: string) =>
    api.get<Bill[]>("/api/v1/bills", { params: status ? { status } : {} }),
  getTrending: () => api.get<Bill[]>("/api/v1/bills/trending"),
  getBill:     (id: string) => api.get<Bill>(`/api/v1/bills/${id}`),
  getResults:  (id: string) => api.get<BillResults>(`/api/v1/vote/${id}/results`),

  // Identity
  verify: (phone: string, region?: string, gender?: string) =>
    api.post("/api/v1/identity/verify", {
      phone_number: phone,
      region,
      gender_code: gender,
    }),
};

// ─── Fetch Helpers ───────────────────────────────────────────────────────────

async function _get(path: string) {
  const res = await fetch(`${API_URL}/api/v1${path}`);
  return res.json();
}

async function _post(path: string, body: unknown) {
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

// MOD-06: Analytics
export const analytics = {
  overview:       ()              => _get("/analytics/overview"),
  trends:         (days = 30)     => _get(`/analytics/divergence-trends?days=${days}`),
  timeline:       (billId?: string, days = 30) =>
    _get(`/analytics/votes-timeline?days=${days}${billId ? `&bill_id=${billId}` : ""}`),
  topDivergence:  (limit = 10)    => _get(`/analytics/top-divergence?limit=${limit}`),
};

// MOD-12: MP Comparison
export const mp = {
  parties: () => _get("/mp/parties"),
  ranking: () => _get("/mp/ranking"),
  compare: (abbr: string) => _get(`/mp/compare/${encodeURIComponent(abbr)}`),
  bill:    (id: string)   => _get(`/mp/bill/${id}`),
};

// MOD-16: Municipal
export const municipal = {
  periferias: ()              => _get("/periferia"),
  dimoi:      (id: number)    => _get(`/periferia/${id}/dimos`),
  decisions:  ()              => _get("/decisions"),
};

// MOD-14: Export URLs
export const exportUrls = {
  billsCsv:      `${API_URL}/api/v1/export/bills.csv`,
  resultsJson:   `${API_URL}/api/v1/export/results.json`,
  divergenceCsv: `${API_URL}/api/v1/export/divergence.csv`,
};

// MOD-15: Admin
export const adminApi = {
  dashboard:   (key: string) => _get(`/admin/dashboard?admin_key=${key}`),
  bills:       (key: string) => _get(`/admin/bills?admin_key=${key}`),
  stats:       (key: string) => _get(`/admin/stats?admin_key=${key}`),
  reviewBill:  (key: string, id: string, approved = true) =>
    _post(`/admin/bills/${id}/review?admin_key=${key}&approved=${approved}`, {}),
  transition:  (key: string, id: string, newStatus: string) =>
    _post(`/bills/${id}/transition`, { new_status: newStatus, admin_key: key }),
};

// MOD-13: Relevance Voting
export async function voteRelevance(
  billId: string,
  signal: 1 | -1,
  nullifierHash: string
): Promise<{ success: boolean; message: string }> {
  const res = await api.post(`/api/v1/vote/${billId}/relevance`, {
    signal,
    nullifier_hash: nullifierHash,
  });
  return res.data;
}
