import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API_URL } from "./api";
import {
  getInitialBills, getInitialResults, INITIAL_DATA_MAX_AGE_MS, INITIAL_DATA_REVALIDATE_SECONDS,
  INITIAL_DATA_TIMEOUT_MS, responseAgeMs,
} from "./initial-data";

const bill = { id: "BILL-1", title_el: "Νομοσχέδιο", title_en: "Bill", status: "ACTIVE" };
const result = { bill_id: "BILL-1", title_el: "Νομοσχέδιο", title_en: "Bill", citizen_total: 3 };

function json(data: unknown, status = 200, extra: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", Date: new Date().toUTCString(), ...extra },
  });
}

function dated(data: unknown, ageMs: number, extra: Record<string, string> = {}): Response {
  return json(data, 200, { Date: new Date(Date.now() - ageMs).toUTCString(), ...extra });
}

describe("server initial data", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("requests the client's default bills query from the fixed public origin with bounded cache and timeout", async () => {
    fetchMock.mockResolvedValue(json([bill]));
    await expect(getInitialBills("")).resolves.toEqual({ status: "", bills: [bill] });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_URL}/api/v1/bills?limit=11&offset=0&include_institutional=true`);
    expect(init.next).toEqual({ revalidate: INITIAL_DATA_REVALIDATE_SECONDS });
    expect(INITIAL_DATA_REVALIDATE_SECONDS).toBe(60);
    expect(init.signal).toBeInstanceOf(AbortSignal);
    expect(init.credentials).toBeUndefined();
    expect(Object.keys(init.headers).map((key) => key.toLowerCase())).toEqual(["accept"]);
  });

  it("adds an allowlisted URL status and skips unknown statuses without a server fetch", async () => {
    fetchMock.mockResolvedValue(json([bill]));
    await expect(getInitialBills("ACTIVE")).resolves.toEqual({ status: "ACTIVE", bills: [bill] });
    expect(fetchMock.mock.calls[0][0]).toContain("include_institutional=true&status=ACTIVE");
    await expect(getInitialBills("UNKNOWN")).resolves.toBeNull();
    await expect(getInitialBills("active")).resolves.toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps a truthful empty success", async () => {
    fetchMock.mockResolvedValue(json([]));
    await expect(getInitialBills("")).resolves.toEqual({ status: "", bills: [] });
  });

  it.each([
    ["HTTP error", () => json({ detail: "x" }, 503)],
    ["network error", () => Promise.reject(new TypeError("fetch failed"))],
    ["timeout", () => Promise.reject(new DOMException("timeout", "TimeoutError"))],
    ["non-JSON body", () => new Response("<html>", { status: 200 })],
    ["object instead of list", () => json({ data: [bill] })],
    ["item without id", () => json([{ title_el: "x", status: "ACTIVE" }])],
  ])("returns null for bills %s", async (_name, reply) => {
    fetchMock.mockImplementation(reply);
    await expect(getInitialBills("")).resolves.toBeNull();
  });

  it("uses the same full results export with min_votes=1", async () => {
    fetchMock.mockResolvedValue(json({ count: 1, data: [result] }));
    await expect(getInitialResults()).resolves.toEqual([result]);
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_URL}/api/v1/export/results.json?min_votes=1`);
    expect(fetchMock.mock.calls[0][1].next).toEqual({ revalidate: 60 });
  });

  it.each([
    ["HTTP error", () => json({}, 500)],
    ["network error", () => Promise.reject(new TypeError("fetch failed"))],
    ["missing data", () => json({ count: 0 })],
    ["bad item", () => json({ data: [{ bill_id: 1 }] })],
  ])("returns null for results %s", async (_name, reply) => {
    fetchMock.mockImplementation(reply);
    await expect(getInitialResults()).resolves.toBeNull();
  });

  it("keeps an empty results export", async () => {
    fetchMock.mockResolvedValue(json({ count: 0, data: [] }));
    await expect(getInitialResults()).resolves.toEqual([]);
  });

  it.each([
    ["fresh", 0, true],
    ["exactly the max age", INITIAL_DATA_MAX_AGE_MS, true],
    ["one second over the max age", INITIAL_DATA_MAX_AGE_MS + 1000, false],
    ["far expired (failed background refresh)", 3_600_000, false],
  ])("freshness: %s cached response", async (_name, ageMs, accepted) => {
    vi.useFakeTimers({ toFake: ["Date"], now: Date.UTC(2026, 9, 10, 12, 0, 0) });
    try {
      fetchMock.mockResolvedValue(dated([bill], ageMs));
      await expect(getInitialBills("")).resolves.toEqual(accepted ? { status: "", bills: [bill] } : null);
      fetchMock.mockResolvedValue(dated({ data: [result] }, ageMs));
      await expect(getInitialResults()).resolves.toEqual(accepted ? [result] : null);
    } finally {
      vi.useRealTimers();
    }
  });

  it.each([
    ["missing Date", { Date: "" }],
    ["malformed Date", { Date: "yesterday" }],
    ["Date 1h in the future", { Date: new Date(Date.now() + 3_600_000).toUTCString() }],
    ["Age pushing over the limit", { Age: String(INITIAL_DATA_MAX_AGE_MS / 1000 + 1) }],
    ["malformed Age", { Age: "-5" }],
    ["non-numeric Age", { Age: "Infinity" }],
    ["fractional Age", { Age: "1.5" }],
  ] as [string, Record<string, string>][])("fails closed on %s", async (_name, headers) => {
    const res = json([bill], 200, headers);
    if (headers.Date === "") res.headers.delete("date");
    fetchMock.mockResolvedValue(res);
    await expect(getInitialBills("")).resolves.toBeNull();
  });

  it("measures origin age from Date plus Age", () => {
    const now = Date.UTC(2026, 9, 10, 12, 0, 0);
    const at = (s: number) => new Date(now - s * 1000).toUTCString();
    expect(responseAgeMs(new Headers({ date: at(10) }), now)).toBe(10_000);
    expect(responseAgeMs(new Headers({ date: at(10), age: "30" }), now)).toBe(40_000);
    expect(responseAgeMs(new Headers({ date: new Date(now + 4000).toUTCString() }), now)).toBe(-4000);
    expect(responseAgeMs(new Headers({ date: new Date(now + 6000).toUTCString() }), now)).toBeNull();
    expect(responseAgeMs(new Headers(), now)).toBeNull();
  });

  it("keeps an empty success when fresh and drops it when expired", async () => {
    fetchMock.mockResolvedValue(dated([], 1000));
    await expect(getInitialBills("")).resolves.toEqual({ status: "", bills: [] });
    fetchMock.mockResolvedValue(dated([], INITIAL_DATA_MAX_AGE_MS + 5000));
    await expect(getInitialBills("")).resolves.toBeNull();
  });

  it("returns null when the fetch never settles within the page deadline", async () => {
    vi.useFakeTimers();
    try {
      fetchMock.mockImplementation(() => new Promise(() => {}));
      const pending = getInitialResults();
      await vi.advanceTimersByTimeAsync(INITIAL_DATA_TIMEOUT_MS);
      await expect(pending).resolves.toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });
});
