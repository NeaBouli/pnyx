/**
 * Ekklesia.gr API Client
 * Kommuniziert mit FastAPI Backend (apps/api)
 * Copyright (c) 2026 Vendetta Labs — MIT License
 */
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
