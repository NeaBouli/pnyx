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

export async function fetchBills(): Promise<Bill[]> {
  return request<Bill[]>("/api/v1/bills");
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
