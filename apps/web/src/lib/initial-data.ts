/**
 * Server-side first-page data for the public /bills and /results routes.
 * Copyright (c) 2026 V-Labs Development — MIT License
 *
 * Same public GET endpoints and query as the client (src/lib/api.ts), fetched
 * once on the server so the first cards are in the initial HTML. Any failure
 * returns null and the client falls back to its own mount fetch; a failure is
 * never turned into an empty list. No cookies, headers or identity are sent.
 */
import { API_URL, type Bill, type PublishedResult } from "./api";

// Collapses bursts of page views into one upstream request per cache key.
// This is NOT a freshness bound: Next 16 serves an expired entry while it
// refreshes in the background and keeps it when the refresh fails (non-200 or
// network error), so the cached copy can be arbitrarily old.
export const INITIAL_DATA_REVALIDATE_SECONDS = 60;
// Freshness is enforced here instead: a response whose origin Date (+ Age) is
// older than this is not rendered and the client fetches live data. 120s is
// two revalidate windows: under steady traffic an entry is refreshed once it
// passes 60s, so healthy data stays below the limit; a failing or idle API
// only costs the SSR seed, never shows an older #456 visibility state.
export const INITIAL_DATA_MAX_AGE_MS = 120_000;
// Date has 1s resolution and the API normally runs on the same host; a Date
// further in the future than this means an untrustworthy clock -> fail closed.
export const INITIAL_DATA_CLOCK_SKEW_MS = 5_000;
// Bounds how long the page waits for this helper (below the client axios 10s
// timeout). It does not bound Next's background revalidation, which drops the
// caller's AbortSignal; that refresh can outlive the request.
export const INITIAL_DATA_TIMEOUT_MS = 3000;

export const BILLS_PAGE_SIZE = 10;
// Only these ?status= values are prefetched; anything else keeps the client
// path so user input cannot create unbounded server cache keys.
export const SSR_BILL_STATUSES = ["", "ACTIVE", "WINDOW_24H", "PARLIAMENT_VOTED", "OPEN_END"] as const;

export type InitialBills = { status: string; bills: Bill[] };

/** Origin age of a (possibly cached) response, or null if it cannot be trusted. */
export function responseAgeMs(headers: Headers, now: number): number | null {
  const date = headers.get("date");
  if (!date) return null;
  const dated = Date.parse(date);
  if (!Number.isFinite(dated)) return null;
  const ageHeader = headers.get("age");
  if (ageHeader !== null && !/^\d{1,9}$/.test(ageHeader.trim())) return null;
  const age = now - dated + (ageHeader === null ? 0 : Number(ageHeader.trim()) * 1000);
  if (age < -INITIAL_DATA_CLOCK_SKEW_MS) return null;
  return age;
}

async function readFreshJson(path: string): Promise<unknown> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { Accept: "application/json" },
    next: { revalidate: INITIAL_DATA_REVALIDATE_SECONDS },
    signal: AbortSignal.timeout(INITIAL_DATA_TIMEOUT_MS),
  });
  if (!res.ok) return null;
  // The Next fetch cache keeps the origin headers, so Date is the time the API
  // produced this body, also on a cache hit or a stale-while-revalidate hit.
  const age = responseAgeMs(res.headers, Date.now());
  if (age === null || age > INITIAL_DATA_MAX_AGE_MS) return null;
  return await res.json();
}

async function fetchPublicJson(path: string): Promise<unknown> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = new Promise<null>((resolve) => {
    timer = setTimeout(() => resolve(null), INITIAL_DATA_TIMEOUT_MS);
  });
  try {
    return await Promise.race([readFreshJson(path).catch(() => null), deadline]);
  } finally {
    clearTimeout(timer);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isBill(value: unknown): value is Bill {
  return isRecord(value)
    && typeof value.id === "string"
    && typeof value.title_el === "string"
    && typeof value.status === "string";
}

function isPublishedResult(value: unknown): value is PublishedResult {
  return isRecord(value)
    && typeof value.bill_id === "string"
    && typeof value.title_el === "string"
    && typeof value.citizen_total === "number";
}

export function billsQuery(status: string): string {
  // Mirrors BillsClient default params: limit PAGE_SIZE+1, offset 0, institutional on.
  const query = new URLSearchParams({
    limit: String(BILLS_PAGE_SIZE + 1),
    offset: "0",
    include_institutional: "true",
  });
  if (status) query.set("status", status);
  return query.toString();
}

export async function getInitialBills(status: string): Promise<InitialBills | null> {
  if (!(SSR_BILL_STATUSES as readonly string[]).includes(status)) return null;
  const body = await fetchPublicJson(`/api/v1/bills?${billsQuery(status)}`);
  if (!Array.isArray(body) || !body.every(isBill)) return null;
  return { status, bills: body };
}

export async function getInitialResults(): Promise<PublishedResult[] | null> {
  const body = await fetchPublicJson("/api/v1/export/results.json?min_votes=1");
  if (!isRecord(body) || !Array.isArray(body.data) || !body.data.every(isPublishedResult)) return null;
  return body.data;
}
