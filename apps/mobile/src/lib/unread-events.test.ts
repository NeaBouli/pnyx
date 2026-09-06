import { describe, expect, it, vi } from "vitest";
import {
  canonicalTemplateId,
  createUnreadEventsStore,
  extractPushData,
  isSafeBillId,
  parseUnreadLedger,
  stableEventId,
  MAX_UNREAD_EVENTS,
  MAX_READ_TOMBSTONES,
  UNREAD_EVENTS_STORAGE_KEY,
  UNREAD_FEED_SNAPSHOT_KEY,
  type UnreadEventsStore,
} from "./unread-events";

function memoryStorage(initial: Record<string, string> = {}) {
  const map = new Map<string, string>(Object.entries(initial));
  return {
    map,
    getItem: vi.fn(async (key: string) => map.get(key) ?? null),
    setItem: vi.fn(async (key: string, value: string) => {
      map.set(key, value);
    }),
  };
}

function makeStore(storage = memoryStorage(), enabled = true) {
  return createUnreadEventsStore({
    getItem: storage.getItem,
    setItem: storage.setItem,
    isEnabled: async () => enabled,
  });
}

const BILL = "bill-abc123";
const DIAV_BILL = "DIAV-Ρ9Ζ546ΜΤΛΒ-Η";

function billPayload(template: string, billId = BILL) {
  return { template_id: template, bill_id: billId, title: "T", body: "B" };
}

describe("stable event IDs", () => {
  it("normalizes template aliases to canonical IDs", () => {
    expect(canonicalTemplateId("new_bill")).toBe("vote_open");
    expect(canonicalTemplateId("vote_open")).toBe("vote_open");
    expect(canonicalTemplateId("result")).toBe("vote_result");
    expect(canonicalTemplateId("vote_result")).toBe("vote_result");
    expect(stableEventId(billPayload("new_bill"))).toBe(`vote_open:${BILL}`);
    expect(stableEventId(billPayload("vote_open"))).toBe(`vote_open:${BILL}`);
    expect(stableEventId(billPayload("result"))).toBe(`vote_result:${BILL}`);
    expect(stableEventId(billPayload("vote_result"))).toBe(`vote_result:${BILL}`);
  });

  it("rejects unknown templates instead of bucketing them as system_update", () => {
    for (const name of ["constructor", "__proto__", "toString"]) {
      expect(canonicalTemplateId(name)).toBeNull();
      expect(stableEventId(billPayload(name))).toBeNull();
    }
    expect(canonicalTemplateId("bogus")).toBeNull();
    expect(canonicalTemplateId("marketing")).toBeNull();
    expect(canonicalTemplateId(undefined)).toBeNull();
    expect(canonicalTemplateId(42)).toBeNull();
    expect(stableEventId({ template_id: "bogus", bill_id: BILL })).toBeNull();
    expect(stableEventId({ template_id: "bogus", event_id: "x" })).toBeNull();
    expect(stableEventId({ event_id: "x" })).toBeNull();
  });

  it("lets canonical bill template+ID take precedence over an explicit event_id", () => {
    expect(
      stableEventId({ template_id: "new_bill", bill_id: BILL, event_id: "push-123" }),
    ).toBe(`vote_open:${BILL}`);
    expect(
      stableEventId({ template_id: "result", bill_id: BILL, event_id: "push-456" }),
    ).toBe(`vote_result:${BILL}`);
  });

  it("prefers an explicit event_id for weekly/system events", () => {
    expect(
      stableEventId({ template_id: "weekly_digest", event_id: "2026-W36" }),
    ).toBe("weekly_digest:evt:2026-W36");
    expect(
      stableEventId({ template_id: "system_update", event_id: "v1.0.33" }),
    ).toBe("system_update:evt:v1.0.33");
  });

  it("uses explicit version or date when no event_id is present", () => {
    expect(stableEventId({ template_id: "system_update", version: "62" })).toBe(
      "system_update:v:62",
    );
    expect(
      stableEventId({ template_id: "weekly_digest", date: "2026-09-06" }),
    ).toBe("weekly_digest:d:2026-09-06");
  });

  it("drops weekly/system events without an explicit stable ID (no content hash fallback)", () => {
    expect(
      stableEventId({ template_id: "weekly_digest", title: "T", body: "B" }),
    ).toBeNull();
    expect(
      stableEventId({ template_id: "system_update", title: "T", body: "B" }),
    ).toBeNull();
  });

  it("drops events without any stable identity", () => {
    expect(stableEventId({ template_id: "weekly_digest" })).toBeNull();
    expect(stableEventId({})).toBeNull();
    expect(stableEventId({ bill_id: "https://evil.example/x" })).toBeNull();
  });

  it("accepts Greek DIAV bill IDs and rejects paths and URLs", () => {
    expect(isSafeBillId("bill-ABC_123")).toBe(true);
    expect(isSafeBillId(DIAV_BILL)).toBe(true);
    expect(isSafeBillId("DIAV-ω123_αβ")).toBe(true);
    expect(isSafeBillId("https://evil.example")).toBe(false);
    expect(isSafeBillId("https://evil.example/DIAV-x")).toBe(false);
    expect(isSafeBillId("../secret")).toBe(false);
    expect(isSafeBillId("DIAV/Ρ9Ζ546ΜΤΛΒ")).toBe(false);
    expect(isSafeBillId("DIAV-Ρ9Ζ546ΜΤΛΒ.json")).toBe(false);
    expect(isSafeBillId("")).toBe(false);
    expect(isSafeBillId("x".repeat(65))).toBe(false);
  });

  it("derives stable IDs from Greek DIAV bill IDs", () => {
    expect(stableEventId(billPayload("new_bill", DIAV_BILL))).toBe(
      `vote_open:${DIAV_BILL}`,
    );
    expect(stableEventId(billPayload("result", DIAV_BILL))).toBe(
      `vote_result:${DIAV_BILL}`,
    );
  });
});

describe("push payload extraction", () => {
  const data = { template_id: "new_bill", bill_id: BILL };

  it("unwraps raw, nested, dataString, foreground and tap shapes", () => {
    expect(extractPushData(data)).toEqual(data);
    expect(extractPushData({ data })).toEqual(data);
    expect(extractPushData({ data: { dataString: JSON.stringify(data) } })).toMatchObject(data);
    expect(
      extractPushData({ request: { content: { data } } }),
    ).toEqual(data);
    expect(
      extractPushData({
        notification: { request: { content: { data } } },
        actionIdentifier: "expo.modules.notifications.actions.DEFAULT",
      }),
    ).toEqual(data);
    expect(extractPushData("junk")).toBeNull();
    expect(extractPushData({ data: { dataString: "{not json" } })).toEqual({
      dataString: "{not json",
    });
  });
});

describe("unread ledger", () => {
  it("deduplicates foreground/background/tap replays of the same push", async () => {
    const store = makeStore();
    expect(await store.ingest(billPayload("new_bill"))).toBe("added");
    expect(await store.ingest(billPayload("new_bill"))).toBe("duplicate");
    // Alias template of the same logical event is also a duplicate.
    expect(await store.ingest(billPayload("vote_open"))).toBe("duplicate");
    expect(await store.unreadCount()).toBe(1);
  });

  it("drops pushes with unknown templates as invalid", async () => {
    const store = makeStore();
    expect(
      await store.ingest({ template_id: "marketing", event_id: "m1", title: "T" }),
    ).toBe("invalid");
    expect(await store.ingest(billPayload("marketing"))).toBe("invalid");
    expect(await store.unreadCount()).toBe(0);
  });

  it("persists dedup state across an app restart", async () => {
    const storage = memoryStorage();
    const first = makeStore(storage);
    await first.ingest(billPayload("new_bill"));
    await first.ingest(billPayload("result"));

    const restarted = makeStore(storage);
    expect(await restarted.unreadCount()).toBe(2);
    expect(await restarted.ingest(billPayload("new_bill"))).toBe("duplicate");
    expect(await restarted.unreadCount()).toBe(2);
  });

  it("round-trips Greek DIAV bill events through persistence", async () => {
    const storage = memoryStorage();
    const first = makeStore(storage);
    expect(await first.ingest(billPayload("new_bill", DIAV_BILL))).toBe("added");

    const restarted = makeStore(storage);
    const events = await restarted.list();
    expect(events.map((e) => e.id)).toEqual([`vote_open:${DIAV_BILL}`]);
    expect(events[0].billId).toBe(DIAV_BILL);
    expect(await restarted.ingest(billPayload("vote_open", DIAV_BILL))).toBe(
      "duplicate",
    );
  });

  it("acknowledges events per ID and keeps tombstones against replays", async () => {
    const storage = memoryStorage();
    const store = makeStore(storage);
    await store.ingest(billPayload("new_bill"));
    expect(await store.markRead(`vote_open:${BILL}`)).toBe(true);
    expect(await store.unreadCount()).toBe(0);
    // Replay after read stays a duplicate thanks to the tombstone.
    expect(await store.ingest(billPayload("new_bill"))).toBe("duplicate");
    expect(await store.markRead("unknown-id")).toBe(false);

    const restarted = makeStore(storage);
    expect(await restarted.ingest(billPayload("new_bill"))).toBe("duplicate");
    expect(await restarted.unreadCount()).toBe(0);
  });

  it("serializes concurrent delivery into a single event", async () => {
    const store = makeStore();
    const results = await Promise.all(
      Array.from({ length: 8 }, () => store.ingest(billPayload("new_bill"))),
    );
    expect(results.filter((r) => r === "added")).toHaveLength(1);
    expect(results.filter((r) => r === "duplicate")).toHaveLength(7);
    expect(await store.unreadCount()).toBe(1);
  });

  it("recovers from malformed persisted data", async () => {
    for (const junk of [
      "not json at all",
      '{"events": "nope", "read": 5}',
      '{"events":[{"id":1},{"id":"ok","templateId":"bogus"}],"read":[]}',
      "[]",
      "null",
    ]) {
      const storage = memoryStorage({ [UNREAD_EVENTS_STORAGE_KEY]: junk });
      const store = makeStore(storage);
      expect(await store.unreadCount()).toBe(0);
      expect(await store.ingest(billPayload("new_bill"))).toBe("added");
      expect(await store.unreadCount()).toBe(1);
    }
  });

  it("drops tombstoned and duplicated events from malformed snapshots", () => {
    const state = parseUnreadLedger(
      JSON.stringify({
        events: [
          { id: "vote_open:b1", templateId: "vote_open", title: "a", body: "b", billId: "b1" },
          { id: "vote_open:b1", templateId: "vote_open", title: "dup", body: "", billId: "b1" },
          { id: "vote_result:b2", templateId: "vote_result", title: "r", body: "", billId: "b2" },
          { id: "bad id with spaces", templateId: "vote_open", title: "", body: "", billId: null },
        ],
        read: ["vote_result:b2"],
      }),
    );
    expect(state.events.map((e) => e.id)).toEqual(["vote_open:b1"]);
    expect(state.read).toEqual(["vote_result:b2"]);
  });

  it("bounds the ledger and the tombstone list", async () => {
    const storage = memoryStorage();
    const store = makeStore(storage);
    for (let i = 0; i < MAX_UNREAD_EVENTS + 25; i += 1) {
      await store.ingest(billPayload("new_bill", `bill-${i}`));
    }
    expect(await store.unreadCount()).toBe(MAX_UNREAD_EVENTS);

    const events = await store.list();
    for (const event of events) await store.markRead(event.id);
    expect(await store.unreadCount()).toBe(0);

    const persisted = JSON.parse(storage.map.get(UNREAD_EVENTS_STORAGE_KEY)!);
    expect(persisted.read.length).toBeLessThanOrEqual(MAX_READ_TOMBSTONES);
    expect(persisted.events).toHaveLength(0);
  });

  it("tombstones unread events evicted by the ledger bound", async () => {
    const storage = memoryStorage();
    const store = makeStore(storage);
    for (let i = 0; i <= MAX_UNREAD_EVENTS; i += 1) {
      await store.ingest(billPayload("new_bill", `bill-${i}`));
    }
    expect(await store.unreadCount()).toBe(MAX_UNREAD_EVENTS);

    // bill-0 was evicted while still unread; its replay stays deduplicated.
    expect(await store.ingest(billPayload("new_bill", "bill-0"))).toBe("duplicate");
    expect(await store.unreadCount()).toBe(MAX_UNREAD_EVENTS);

    const persisted = JSON.parse(storage.map.get(UNREAD_EVENTS_STORAGE_KEY)!);
    expect(persisted.read).toContain("vote_open:bill-0");
    expect(persisted.read.length).toBeLessThanOrEqual(MAX_READ_TOMBSTONES);
  });

  it("respects master/category preference state on ingest", async () => {
    const disabled = makeStore(memoryStorage(), false);
    expect(await disabled.ingest(billPayload("new_bill"))).toBe("disabled");
    expect(await disabled.unreadCount()).toBe(0);

    // Disabled events are not tombstoned: re-enabling lets a redelivery in.
    const storage = memoryStorage();
    let enabled = false;
    const store = createUnreadEventsStore({
      getItem: storage.getItem,
      setItem: storage.setItem,
      isEnabled: async () => enabled,
    });
    expect(await store.ingest(billPayload("new_bill"))).toBe("disabled");
    enabled = true;
    expect(await store.ingest(billPayload("new_bill"))).toBe("added");
  });

  it("category acknowledgement leaves unrelated categories unread", async () => {
    const store = makeStore();
    await store.ingest(billPayload("new_bill"));
    await store.ingest(billPayload("result"));
    await store.ingest({ template_id: "system_update", event_id: "v62", title: "S", body: "" });

    expect(await store.markCategoryRead("push_vote_open")).toBe(1);
    const remaining = await store.list();
    expect(remaining.map((e) => e.id)).toEqual([
      `vote_result:${BILL}`,
      "system_update:evt:v62",
    ]);

    expect(await store.markAllRead()).toBe(2);
    expect(await store.unreadCount()).toBe(0);
  });

  it("notifies subscribers on mutation", async () => {
    const store = makeStore();
    const seen: number[] = [];
    const unsubscribe = store.subscribe((events) => seen.push(events.length));
    await store.ingest(billPayload("new_bill"));
    await store.ingest(billPayload("result"));
    await store.markRead(`vote_open:${BILL}`);
    unsubscribe();
    await store.ingest(billPayload("new_bill", "other-bill"));
    expect(seen).toEqual([1, 2, 1]);
  });
});

describe("F-Droid foreground bill refresh", () => {
  const bill = (id: string, status: string) => ({
    id,
    status,
    title_el: `Νομοσχέδιο ${id}`,
  });

  it("seeds the baseline snapshot without flooding old bills as new", async () => {
    const store = makeStore();
    const first = await store.refreshFromBills([
      bill("b1", "ACTIVE"),
      bill("b2", "PARLIAMENT_VOTED"),
      bill("b3", "OPEN_END"),
    ]);
    expect(first).toEqual({ added: 0, seeded: true });
    expect(await store.unreadCount()).toBe(0);
  });

  it("maps the real BillStatus values to feed events without inventing states", async () => {
    const store = makeStore();
    await store.refreshFromBills([bill("b1", "ANNOUNCED")]); // baseline

    const refresh = await store.refreshFromBills([
      bill("b1", "WINDOW_24H"), // transition into the 24h window
      bill("b2", "ANNOUNCED"), // brand new announced bill
      bill("b3", "OPEN_END"), // archival state: no event
    ]);
    expect(refresh).toEqual({ added: 2, seeded: false });
    expect((await store.list()).map((e) => e.id)).toEqual([
      "vote_24h:b1",
      "bill_announced:b2",
    ]);
  });

  it("adds only new bills and status transitions afterwards", async () => {
    const store = makeStore();
    await store.refreshFromBills([bill("b1", "OPEN_END")]);

    const second = await store.refreshFromBills([
      bill("b1", "ACTIVE"), // transition
      bill("b2", "ACTIVE"), // brand new bill
      bill("b3", "OPEN_END"), // new but archival, not a voting state
    ]);
    expect(second).toEqual({ added: 2, seeded: false });
    expect((await store.list()).map((e) => e.id)).toEqual([
      "vote_open:b1",
      "vote_open:b2",
    ]);

    const third = await store.refreshFromBills([
      bill("b1", "PARLIAMENT_VOTED"),
      bill("b2", "ACTIVE"),
    ]);
    expect(third).toEqual({ added: 1, seeded: false });
    expect((await store.list()).map((e) => e.id)).toEqual([
      "vote_open:b1",
      "vote_open:b2",
      "vote_result:b1",
    ]);

    // Identical refresh is a no-op.
    const fourth = await store.refreshFromBills([
      bill("b1", "PARLIAMENT_VOTED"),
      bill("b2", "ACTIVE"),
    ]);
    expect(fourth).toEqual({ added: 0, seeded: false });
  });

  it("shares canonical IDs with pushes so neither path duplicates", async () => {
    const store = makeStore();
    await store.refreshFromBills([bill("b1", "ANNOUNCED")]);

    // Push arrives first for the transition.
    expect(await store.ingest(billPayload("new_bill", "b1"))).toBe("added");
    const refresh = await store.refreshFromBills([bill("b1", "ACTIVE")]);
    expect(refresh.added).toBe(0);
    expect(await store.unreadCount()).toBe(1);

    // And the reverse: feed first, push replay second.
    const store2 = makeStore();
    await store2.refreshFromBills([bill("b9", "ANNOUNCED")]);
    await store2.refreshFromBills([bill("b9", "ACTIVE")]);
    expect(await store2.ingest(billPayload("vote_open", "b9"))).toBe("duplicate");
  });

  it("deduplicates refresh events across a restart", async () => {
    const storage = memoryStorage();
    const first = makeStore(storage);
    await first.refreshFromBills([bill("b1", "ANNOUNCED")]);
    await first.refreshFromBills([bill("b1", "ACTIVE")]);

    const restarted = makeStore(storage);
    expect(await restarted.unreadCount()).toBe(1);
    const again = await restarted.refreshFromBills([bill("b1", "ACTIVE")]);
    expect(again).toEqual({ added: 0, seeded: false });
  });

  it("ignores an invalid non-array feed without wiping the snapshot", async () => {
    const storage = memoryStorage();
    const store = makeStore(storage);
    await store.refreshFromBills([bill("b1", "ACTIVE")]);
    const before = storage.map.get(UNREAD_FEED_SNAPSHOT_KEY);

    for (const junk of ["nope", 42, null, {}, undefined]) {
      expect(await store.refreshFromBills(junk)).toEqual({
        added: 0,
        seeded: false,
      });
    }
    expect(storage.map.get(UNREAD_FEED_SNAPSHOT_KEY)).toBe(before);

    // The preserved baseline still detects the later transition.
    const next = await store.refreshFromBills([bill("b1", "PARLIAMENT_VOTED")]);
    expect(next).toEqual({ added: 1, seeded: false });
    expect((await store.list()).map((e) => e.id)).toEqual(["vote_result:b1"]);
  });

  it("reseeds the baseline from a malformed snapshot without flooding", async () => {
    for (const junk of ["{broken", "{}", '"text"', "123", "[null]", '[["b1", "ACTIVE"], ["bad/path", "ACTIVE"]]']) {
      const storage = memoryStorage({
        [UNREAD_FEED_SNAPSHOT_KEY]: junk,
        [UNREAD_EVENTS_STORAGE_KEY]: "{also broken",
      });
      const store = makeStore(storage);
      const result = await store.refreshFromBills([
        bill("b1", "ACTIVE"),
        bill("b2", "PARLIAMENT_VOTED"),
      ]);
      expect(result).toEqual({ added: 0, seeded: true });
      expect(await store.unreadCount()).toBe(0);

      // The rewritten snapshot is a valid baseline for the next refresh.
      const next = await store.refreshFromBills([
        bill("b1", "PARLIAMENT_VOTED"),
        bill("b2", "PARLIAMENT_VOTED"),
      ]);
      expect(next).toEqual({ added: 1, seeded: false });
      expect((await store.list()).map((e) => e.id)).toEqual(["vote_result:b1"]);
    }
  });

  it("preserves the bounded prior snapshot across partial feed results", async () => {
    const storage = memoryStorage();
    const store = makeStore(storage);
    await store.refreshFromBills([bill("b1", "ACTIVE"), bill("b2", "ACTIVE")]);

    // Partial feed: b2 is absent but its status must survive.
    const partial = await store.refreshFromBills([bill("b1", "ACTIVE")]);
    expect(partial).toEqual({ added: 0, seeded: false });
    const snapshot = new Map<string, string>(
      JSON.parse(storage.map.get(UNREAD_FEED_SNAPSHOT_KEY)!),
    );
    expect(snapshot.get("b1")).toBe("ACTIVE");
    expect(snapshot.get("b2")).toBe("ACTIVE");

    // b2's preserved baseline still detects its transition later.
    const later = await store.refreshFromBills([bill("b2", "PARLIAMENT_VOTED")]);
    expect(later).toEqual({ added: 1, seeded: false });
    expect((await store.list()).map((e) => e.id)).toEqual(["vote_result:b2"]);
  });

  it("saves the feed snapshot only after ledger ingest succeeded", async () => {
    const storage = memoryStorage();
    let failLedgerWrites = false;
    const store = createUnreadEventsStore({
      getItem: storage.getItem,
      setItem: async (key, value) => {
        if (failLedgerWrites && key === UNREAD_EVENTS_STORAGE_KEY) {
          throw new Error("ledger disk full");
        }
        await storage.setItem(key, value);
      },
      isEnabled: async () => true,
    });

    // Seed a valid baseline (no candidates, snapshot write succeeds).
    await store.refreshFromBills([bill("b1", "OPEN_END")]);
    expect(storage.map.get(UNREAD_FEED_SNAPSHOT_KEY)).toBe(
      JSON.stringify([["b1", "OPEN_END"]]),
    );

    // Ledger ingest fails: the refresh rejects and the snapshot is untouched.
    failLedgerWrites = true;
    await expect(store.refreshFromBills([bill("b1", "ACTIVE")])).rejects.toThrow(
      "ledger disk full",
    );
    expect(storage.map.get(UNREAD_FEED_SNAPSHOT_KEY)).toBe(
      JSON.stringify([["b1", "OPEN_END"]]),
    );

    // The unchanged snapshot replays the transition once writes recover.
    failLedgerWrites = false;
    const retry = await store.refreshFromBills([bill("b1", "ACTIVE")]);
    expect(retry).toEqual({ added: 1, seeded: false });
    expect(storage.map.get(UNREAD_FEED_SNAPSHOT_KEY)).toBe(
      JSON.stringify([["b1", "ACTIVE"]]),
    );
    expect((await store.list()).map((e) => e.id)).toEqual(["vote_open:b1"]);
  });

  it("rejects the refresh when the snapshot read fails and keeps the old snapshot", async () => {
    const storage = memoryStorage();
    const writer = makeStore(storage);
    await writer.refreshFromBills([bill("b1", "ACTIVE")]);
    const before = storage.map.get(UNREAD_FEED_SNAPSHOT_KEY);

    const failing = createUnreadEventsStore({
      getItem: async (key) => {
        if (key === UNREAD_FEED_SNAPSHOT_KEY) throw new Error("read fail");
        return storage.getItem(key);
      },
      setItem: storage.setItem,
      isEnabled: async () => true,
    });
    await expect(
      failing.refreshFromBills([bill("b1", "PARLIAMENT_VOTED")]),
    ).rejects.toThrow("read fail");
    expect(storage.map.get(UNREAD_FEED_SNAPSHOT_KEY)).toBe(before);
  });
});

describe("store queue", () => {
  it("rejects on storage read failure without caching an empty ledger", async () => {
    const storage = memoryStorage();
    const writer = makeStore(storage);
    await writer.ingest(billPayload("new_bill"));

    let failReads = true;
    const store = createUnreadEventsStore({
      getItem: async (key) => {
        if (failReads) throw new Error("read fail");
        return storage.getItem(key);
      },
      setItem: storage.setItem,
      isEnabled: async () => true,
    });
    await expect(store.unreadCount()).rejects.toThrow("read fail");
    await expect(store.ingest(billPayload("result"))).rejects.toThrow("read fail");

    failReads = false;
    // The real persisted state is still there — no empty ledger was cached.
    expect(await store.unreadCount()).toBe(1);
    expect(await store.ingest(billPayload("new_bill"))).toBe("duplicate");
  });

  it("failed writes leave cached state untouched and a retry persists", async () => {
    const storage = memoryStorage();
    let failWrites = true;
    const store: UnreadEventsStore = createUnreadEventsStore({
      getItem: storage.getItem,
      setItem: async (key, value) => {
        if (failWrites) throw new Error("disk full");
        await storage.setItem(key, value);
      },
      isEnabled: async () => true,
    });

    await expect(store.ingest(billPayload("new_bill"))).rejects.toThrow("disk full");
    // The failed mutation never reached the cache or the storage.
    expect(await store.unreadCount()).toBe(0);
    expect(storage.map.has(UNREAD_EVENTS_STORAGE_KEY)).toBe(false);

    failWrites = false;
    // The retry persists durably.
    expect(await store.ingest(billPayload("new_bill"))).toBe("added");
    expect(await store.unreadCount()).toBe(1);
    const persisted = JSON.parse(storage.map.get(UNREAD_EVENTS_STORAGE_KEY)!);
    expect(persisted.events).toHaveLength(1);

    // The queue survives further write failures and keeps serving reads.
    failWrites = true;
    await expect(store.ingest(billPayload("result"))).rejects.toThrow("disk full");
    expect(await store.unreadCount()).toBe(1);
    failWrites = false;
    expect(await store.ingest(billPayload("result"))).toBe("added");
    expect(await store.unreadCount()).toBe(2);
  });
});
