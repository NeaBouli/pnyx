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

// Public aggregate lists; 60s bounds staleness against API #456 visibility
// changes while collapsing bursts of page views into one upstream request.
export const INITIAL_DATA_REVALIDATE_SECONDS = 60;
// Below the client axios timeout (10s): a slow API should not hold the HTML.
export const INITIAL_DATA_TIMEOUT_MS = 3000;

export const BILLS_PAGE_SIZE = 10;
// Only these ?status= values are prefetched; anything else keeps the client
// path so user input cannot create unbounded server cache keys.
export const SSR_BILL_STATUSES = ["", "ACTIVE", "WINDOW_24H", "PARLIAMENT_VOTED", "OPEN_END"] as const;

export type InitialBills = { status: string; bills: Bill[] };

async function fetchPublicJson(path: string): Promise<unknown> {
  try {
    const res = await fetch(`${API_URL}${path}`, {
      headers: { Accept: "application/json" },
      next: { revalidate: INITIAL_DATA_REVALIDATE_SECONDS },
      signal: AbortSignal.timeout(INITIAL_DATA_TIMEOUT_MS),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
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
