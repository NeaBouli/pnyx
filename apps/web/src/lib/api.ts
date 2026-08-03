/**
 * Ekklesia.gr API Client
 * Kommuniziert mit FastAPI Backend (apps/api)
 * Copyright (c) 2026 V-Labs Development — MIT License
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
  analysis_el?: string | null;
  categories: string[] | null;
  party_votes_parliament: Record<string, string> | null;
  status: string;
  parliament_vote_date: string | null;
  ai_summary_reviewed?: boolean;
  relevance_score?: number;
  forum_topic_id?: number | null;
  parliament_url?: string | null;
  official_source_url?: string | null;
  source?: string | null;
  diavgeia_ada?: string | null;
  governance_level?: string;
  periferia_id?: number | null;
  dimos_id?: number | null;
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
  tier1_vote_count?: number;
  zk_vote_count?: number;
  yes_count: number;
  no_count: number;
  abstain_count: number;
  unknown_count?: number;
  yes_percent: number;
  no_percent: number;
  abstain_percent: number;
  unknown_percent?: number;
  divergence: DivergenceResult | null;
  disclaimer_el: string;
}

export interface PeriferiaSummary {
  id: number;
  name_el: string;
  name_en: string | null;
  code: string;
}

export interface DimosSummary {
  id: number;
  name_el: string;
  name_en: string | null;
  population: number | null;
}

export interface ConsensusRepresentationBill {
  bill_id: string;
  title_el: string;
  governance_level: string;
  dimos_id: number | null;
  periferia_id: number | null;
  org_label: string | null;
  diavgeia_ada: string | null;
  consensus_score: number;
  consensus_count: number;
  updated_at: string | null;
}

export interface ConsensusRepresentationView {
  view: "municipal" | "regional" | "national";
  available: boolean;
  bill_count: number;
  consensus_vote_count: number;
  weighted_score: number | null;
  bills: ConsensusRepresentationBill[];
}

export interface ConsensusRepresentationCoverage {
  total_diavgeia_bills: number;
  geographically_represented_bills: number;
  institutional_or_unresolved_bills: number;
  geographic_mapping_gaps: number;
  complete_geographic_representation: boolean;
}

export interface ConsensusRepresentationResponse {
  source: string;
  privacy: "aggregate_only" | string;
  minimum_group_size: number;
  institutional_excluded: boolean;
  unmapped_geographic_excluded: boolean;
  coverage: ConsensusRepresentationCoverage;
  dimos_id: number | null;
  periferia_id: number | null;
  views: {
    municipal: ConsensusRepresentationView;
    regional: ConsensusRepresentationView;
    national: ConsensusRepresentationView;
  };
}

export interface ConsensusRepresentationQuery {
  dimos_id?: number;
  periferia_id?: number;
  limit?: number;
}

// ─── API Calls ────────────────────────────────────────────────────────────────

export const ekklesia = {
  // VAA
  getStatements: () => api.get<Statement[]>("/api/v1/vaa/statements"),
  getParties:    () => api.get<Party[]>("/api/v1/vaa/parties"),
  match: (answers: Record<number, number>) =>
    api.post("/api/v1/vaa/match", { answers }),

  // Parliament
  getBills: (params: BillQueryParams = {}) => {
    const { status_any, ...rest } = params;
    return api.get<Bill[]>("/api/v1/bills", {
      params: {
        limit: 200,
        ...rest,
        ...(status_any?.length ? { status_any: status_any.join(",") } : {}),
        ...(params.status ? { status: params.status } : {}),
      },
    });
  },
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

async function _get<T = unknown>(path: string): Promise<T> {
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
  topDivergence:  (limit = 10)    => _get<{ data?: unknown[] }>(`/analytics/top-divergence?limit=${limit}`),
};

// MOD-12: MP Comparison
export const mp = {
  parties: () => _get("/mp/parties"),
  ranking: () => _get<{ ranking?: unknown[] }>("/mp/ranking"),
  compare: (abbr: string) => _get(`/mp/compare/${encodeURIComponent(abbr)}`),
  bill:    (id: string)   => _get(`/mp/bill/${id}`),
};

// MOD-16: Municipal
export const municipal = {
  periferias: ()              => _get<PeriferiaSummary[]>("/periferia"),
  dimoi:      (id: number)    => _get<DimosSummary[]>(`/periferia/${id}/dimos`),
  decisions:  ()              => _get("/decisions"),
  getConsensusRepresentation: (params: ConsensusRepresentationQuery = {}) =>
    _get<ConsensusRepresentationResponse>(`/consensus/representation${queryString(params)}`),
};

function queryString(params: ConsensusRepresentationQuery): string {
  const search = new URLSearchParams();
  if (params.dimos_id !== undefined) search.set("dimos_id", String(params.dimos_id));
  if (params.periferia_id !== undefined) search.set("periferia_id", String(params.periferia_id));
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  return search.toString() ? `?${search.toString()}` : "";
}

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
  nullifierHash: string,
  signatureHex: string,
): Promise<{ success: boolean; message: string }> {
  const res = await api.post(`/api/v1/vote/${billId}/relevance`, {
    signal,
    nullifier_hash: nullifierHash,
    signature_hex: signatureHex,
  });
  return res.data;
}
export type BillStatusFilter =
  | "ANNOUNCED"
  | "ACTIVE"
  | "WINDOW_24H"
  | "PARLIAMENT_VOTED"
  | "OPEN_END"
  | string;

export interface BillQueryParams {
  status?: BillStatusFilter;
  status_any?: BillStatusFilter[];
  governance?: string;
  source?: string;
  q?: string;
  periferia_id?: number;
  dimos_id?: number;
  include_institutional?: boolean;
  limit?: number;
  offset?: number;
}
