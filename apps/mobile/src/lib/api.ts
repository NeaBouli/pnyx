/**
 * api.ts — API Client για Ekklesia Mobile
 */

const API_BASE = process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── Identity ───────────────────────────────────────────────────────────────

export interface VerifyResponse {
  success: boolean;
  public_key_hex: string;
  private_key_hex: string;
  nullifier_hash: string;
  message: string;
}

export async function verifyIdentity(
  phoneNumber: string,
  ageGroup?: string,
  region?: string,
  genderCode?: string
): Promise<VerifyResponse> {
  return request<VerifyResponse>("/api/v1/identity/verify", {
    method: "POST",
    body: JSON.stringify({
      phone_number: phoneNumber,
      age_group: ageGroup || null,
      region: region || null,
      gender_code: genderCode || null,
    }),
  });
}

export async function checkIdentityStatus(
  nullifierHash: string
): Promise<{ status: string; created_at: string | null }> {
  return request("/api/v1/identity/status", {
    method: "POST",
    body: JSON.stringify({ nullifier_hash: nullifierHash }),
  });
}

// ─── Bills ──────────────────────────────────────────────────────────────────

export interface Bill {
  id: string;
  title_el: string;
  pill_el: string;
  status: string;
  submitted_at: string;
  party_votes_parliament: Record<string, string> | null;
  relevance_score: number;
}

export async function fetchBills(params?: {
  governance?: string;
  source?: string;
  periferia_id?: number;
  dimos_id?: number;
}): Promise<Bill[]> {
  const qs = new URLSearchParams();
  qs.set("limit", "200");
  if (params?.governance) qs.set("governance", params.governance);
  if (params?.source) qs.set("source", params.source);
  if (params?.periferia_id) qs.set("periferia_id", String(params.periferia_id));
  if (params?.dimos_id) qs.set("dimos_id", String(params.dimos_id));
  return request<Bill[]>(`/api/v1/bills?${qs.toString()}`);
}

export async function fetchBill(id: string): Promise<Bill> {
  return request<Bill>(`/api/v1/bills/${id}`);
}

// ─── Voting ─────────────────────────────────────────────────────────────────

export interface VoteResponse {
  success: boolean;
  message: string;
  bill_id: string;
  vote: string;
}

export async function submitVote(
  nullifierHash: string,
  billId: string,
  vote: string,
  signatureHex: string
): Promise<VoteResponse> {
  return request<VoteResponse>("/api/v1/vote", {
    method: "POST",
    body: JSON.stringify({
      nullifier_hash: nullifierHash,
      bill_id: billId,
      vote: vote.toUpperCase(),
      signature_hex: signatureHex,
    }),
  });
}

export async function correctVote(
  nullifierHash: string,
  billId: string,
  vote: string,
  signatureHex: string
): Promise<any> {
  return request<any>(`/api/v1/vote/${encodeURIComponent(billId)}/correct`, {
    method: "PUT",
    body: JSON.stringify({
      nullifier_hash: nullifierHash,
      bill_id: billId,
      vote: vote.toUpperCase(),
      signature_hex: signatureHex,
    }),
  });
}

export interface BillResults {
  bill_id: string;
  title_el: string;
  status: string;
  total_votes: number;
  yes_count: number;
  no_count: number;
  abstain_count: number;
  unknown_count: number;
  yes_percent: number;
  no_percent: number;
  abstain_percent: number;
  divergence: {
    score: number;
    label_el: string;
    citizen_majority: string;
    parliament_result: string | null;
    headline_el: string;
  } | null;
  results_hidden?: boolean;
  parliament_vote_date?: string | null;
  disclaimer_el: string;
}

export async function fetchResults(billId: string): Promise<BillResults> {
  return request<BillResults>(`/api/v1/vote/${billId}/results`);
}

// ─── Trending + Analytics + MP ──────────────────────────────────────────────

export async function fetchTrending(limit = 10): Promise<Bill[]> {
  return request<Bill[]>(`/api/v1/bills/trending?limit=${limit}`);
}

export async function fetchAnalyticsOverview(): Promise<any> {
  return request<any>("/api/v1/analytics/overview");
}

export async function fetchMPRanking(): Promise<any> {
  return request<any>("/api/v1/mp/ranking");
}

// ─── NEA-189: Politician Evaluation ────────────────────────────────────────

export interface Politician {
  ada_number: string;
  role: string;
  region: string;
  org_label: string;
  governance_level: string;
  avg_score: number | null;
  evaluator_count: number;
}

export interface EvalQuestion {
  id: number;
  question_el: string;
  question_en: string | null;
  category: string;
}

export interface EvalScores {
  ada_number: string;
  org_label: string;
  questions: { question_id: number; question_el: string; category: string; avg_score: number | null; vote_count: number }[];
  total_avg: number | null;
  total_evaluations: number;
}

export async function fetchPoliticians(): Promise<Politician[]> {
  return request<Politician[]>("/api/v1/politicians/");
}

export async function fetchPoliticianQuestions(adaNumber: string): Promise<EvalQuestion[]> {
  return request<EvalQuestion[]>(`/api/v1/politicians/${encodeURIComponent(adaNumber)}/questions`);
}

export async function submitEvaluation(
  adaNumber: string,
  nullifierHash: string,
  scores: { question_id: number; score: number }[],
  signatureHex: string,
): Promise<{ ada_number: string; scores_submitted: number }> {
  return request(`/api/v1/politicians/${encodeURIComponent(adaNumber)}/evaluate`, {
    method: "POST",
    body: JSON.stringify({ nullifier_hash: nullifierHash, scores, signature_hex: signatureHex }),
  });
}

export async function fetchPoliticianScores(adaNumber: string): Promise<EvalScores> {
  return request<EvalScores>(`/api/v1/politicians/${encodeURIComponent(adaNumber)}/scores`);
}

export interface MyEvaluation {
  question_id: number;
  score: number;
  updated_at: string | null;
}

export async function fetchMyEvaluation(adaNumber: string, nullifierHash: string): Promise<MyEvaluation[]> {
  return request<MyEvaluation[]>(`/api/v1/politicians/${encodeURIComponent(adaNumber)}/my-evaluation?nullifier_hash=${encodeURIComponent(nullifierHash)}`);
}

export interface MyEvalBulk {
  ada_number: string;
  last_updated: string | null;
}

export async function fetchMyEvaluationsBulk(nullifierHash: string): Promise<MyEvalBulk[]> {
  return request<MyEvalBulk[]>(`/api/v1/politicians/my-evaluations/bulk?nullifier_hash=${encodeURIComponent(nullifierHash)}`);
}
