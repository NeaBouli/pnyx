import { beforeEach, describe, expect, it, vi } from "vitest";

const store = vi.hoisted(() => {
  const data = new Map<string, string>();
  return {
    data,
    getItemAsync: vi.fn(async (k: string) => data.get(k) ?? null),
    setItemAsync: vi.fn(async (k: string, v: string) => void data.set(k, v)),
    deleteItemAsync: vi.fn(async (k: string) => void data.delete(k)),
  };
});
vi.mock("expo-secure-store", () => store);

import { MAX_AGE_MS, MAX_MARKS, clearVoteMarks, loadVoteMarks, recordVoteMark, syncVoteMark, tileVoteLabel } from "./vote-marks";

const OWNER = "a".repeat(64);
const OTHER_OWNER = "b".repeat(64);
const NOW = 1_800_000_000_000;

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

describe("vote marks storage", () => {
  beforeEach(() => {
    store.data.clear();
    store.data.set("ekklesia_nullifier", OWNER);
  });

  it("records a vote without the choice and reads it back", async () => {
    await recordVoteMark("GR-1", false, OWNER, NOW);
    expect(await loadVoteMarks(NOW)).toEqual({ "GR-1": { corrected: false, at: NOW } });
    const raw = store.data.get("ekklesia_vote_marks_v1")!;
    expect(raw).not.toMatch(/YES|NO|ABSTAIN|vote"/);
  });

  it("keeps the corrected flag once set", async () => {
    await recordVoteMark("GR-1", true, OWNER, NOW);
    await recordVoteMark("GR-1", false, OWNER, NOW + 1);
    expect((await loadVoteMarks(NOW + 1))["GR-1"].corrected).toBe(true);
  });

  it("syncs with the server status and removes stale marks", async () => {
    await syncVoteMark("GR-2", { has_voted: true, is_correction: true }, OWNER, NOW);
    expect((await loadVoteMarks(NOW))["GR-2"]).toEqual({ corrected: true, at: NOW });
    await syncVoteMark("GR-2", { has_voted: false, is_correction: false }, OWNER, NOW);
    expect(await loadVoteMarks(NOW)).toEqual({});
  });

  it("ignores marks of a different identity and stores nothing without one", async () => {
    await recordVoteMark("GR-1", false, OWNER, NOW);
    store.data.set("ekklesia_nullifier", OTHER_OWNER);
    expect(await loadVoteMarks(NOW)).toEqual({});
    store.data.delete("ekklesia_nullifier");
    await recordVoteMark("GR-9", false, OWNER, NOW);
    expect(await loadVoteMarks(NOW)).toEqual({});
  });

  it("prunes by age and count", async () => {
    await recordVoteMark("OLD", false, OWNER, NOW - MAX_AGE_MS - 1);
    for (let i = 0; i < MAX_MARKS + 5; i++) await recordVoteMark(`B-${i}`, false, OWNER, NOW + i);
    const marks = await loadVoteMarks(NOW + MAX_MARKS + 5);
    expect(Object.keys(marks)).toHaveLength(MAX_MARKS);
    expect(marks.OLD).toBeUndefined();
    expect(marks["B-0"]).toBeUndefined();
  });

  it("never throws on corrupt storage", async () => {
    store.data.set("ekklesia_vote_marks_v1", "{not json");
    expect(await loadVoteMarks(NOW)).toEqual({});
    await expect(recordVoteMark("GR-1", false, OWNER, NOW)).resolves.toBeUndefined();
  });
});

describe("vote marks clearing", () => {
  beforeEach(() => {
    store.data.clear();
    store.data.set("ekklesia_nullifier", OWNER);
    store.setItemAsync.mockClear();
    store.deleteItemAsync.mockClear();
  });

  it("reports a deletion error without poisoning the mutation queue", async () => {
    await recordVoteMark("GR-1", false, OWNER, NOW);
    store.deleteItemAsync.mockRejectedValueOnce(new Error("storage unavailable"));

    await expect(clearVoteMarks()).rejects.toThrow("storage unavailable");
    await clearVoteMarks();

    expect(store.data.has("ekklesia_vote_marks_v1")).toBe(false);
    await recordVoteMark("GR-2", false, OWNER, NOW);
    expect((await loadVoteMarks(NOW))["GR-2"]).toBeDefined();
  });

  it.each([true, false])("physically removes stored marks with current identity=%s", async (hasIdentity) => {
    await recordVoteMark("GR-1", true, OWNER, NOW);
    expect(store.data.has("ekklesia_vote_marks_v1")).toBe(true);
    if (!hasIdentity) store.data.delete("ekklesia_nullifier");

    await clearVoteMarks();

    expect(await loadVoteMarks(NOW)).toEqual({});
    expect(store.data.has("ekklesia_vote_marks_v1")).toBe(false);
    expect(store.deleteItemAsync).toHaveBeenCalledExactlyOnceWith("ekklesia_vote_marks_v1");
    expect(store.data.get("ekklesia_nullifier")).toBe(hasIdentity ? OWNER : undefined);
  });

  it.each(["record", "sync"] as const)("waits behind an in-flight %s write before clearing", async (operation) => {
    await recordVoteMark("existing", false, OWNER, NOW);
    const writeStarted = deferred<void>();
    const releaseWrite = deferred<void>();
    store.setItemAsync.mockImplementationOnce(async (key, value) => {
      writeStarted.resolve(undefined);
      await releaseWrite.promise;
      store.data.set(key, value);
    });
    const update = operation === "record"
      ? recordVoteMark("GR-1", true, OWNER, NOW + 1)
      : syncVoteMark("GR-1", { has_voted: true, is_correction: false }, OWNER, NOW + 1);
    await writeStarted.promise;
    const clearing = clearVoteMarks();

    try {
      expect(store.deleteItemAsync).not.toHaveBeenCalled();
      expect(store.data.has("ekklesia_vote_marks_v1")).toBe(true);
    } finally {
      releaseWrite.resolve(undefined);
      await Promise.all([update, clearing]);
    }

    expect(store.deleteItemAsync).toHaveBeenCalledExactlyOnceWith("ekklesia_vote_marks_v1");
    expect(store.data.has("ekklesia_vote_marks_v1")).toBe(false);
    expect(await loadVoteMarks(NOW + 1)).toEqual({});
    expect(store.data.get("ekklesia_nullifier")).toBe(OWNER);
  });
});

describe("vote marks follow-ups (#487 review)", () => {
  beforeEach(() => {
    store.data.clear();
    store.data.set("ekklesia_nullifier", OWNER);
  });

  it("stores the server's can_correct and refreshes the timestamp on sync", async () => {
    await recordVoteMark("GR-5", false, OWNER, NOW - 1000);
    await syncVoteMark("GR-5", { has_voted: true, is_correction: false, can_correct: true }, OWNER, NOW);
    expect((await loadVoteMarks(NOW))["GR-5"]).toEqual({ corrected: false, at: NOW, correctable: true });
  });

  it("a later local vote makes correctability unknown again", async () => {
    await syncVoteMark("GR-6", { has_voted: true, is_correction: false, can_correct: true }, OWNER, NOW);
    await recordVoteMark("GR-6", true, OWNER, NOW + 1);
    expect((await loadVoteMarks(NOW + 1))["GR-6"].correctable).toBeUndefined();
  });

  it("concurrent updates do not overwrite each other", async () => {
    await Promise.all([
      recordVoteMark("A", false, OWNER, NOW),
      syncVoteMark("B", { has_voted: true, is_correction: false, can_correct: false }, OWNER, NOW),
      recordVoteMark("C", true, OWNER, NOW),
      recordVoteMark("D", false, OWNER, NOW),
      syncVoteMark("E", { has_voted: true, is_correction: true }, OWNER, NOW),
    ]);
    expect(Object.keys(await loadVoteMarks(NOW)).sort()).toEqual(["A", "B", "C", "D", "E"]);
  });
});

describe("vote marks originating owner", () => {
  beforeEach(() => {
    store.data.clear();
    store.data.set("ekklesia_nullifier", OWNER);
    store.setItemAsync.mockClear();
  });

  it.each([false, true])("discards a late vote/correction result from A after switching to B (corrected=%s)", async (corrected) => {
    const response = deferred<void>();
    const pending = response.promise.then(() => recordVoteMark("GR-1", corrected, OWNER, NOW + 1));
    store.data.set("ekklesia_nullifier", OTHER_OWNER);
    await recordVoteMark("GR-1", true, OTHER_OWNER, NOW);
    await recordVoteMark("B-only", false, OTHER_OWNER, NOW);
    const before = store.data.get("ekklesia_vote_marks_v1");
    store.setItemAsync.mockClear();

    response.resolve(undefined);
    await pending;

    expect(store.setItemAsync).not.toHaveBeenCalled();
    expect(store.data.get("ekklesia_vote_marks_v1")).toBe(before);
    expect(await loadVoteMarks(NOW + 1)).toEqual({
      "GR-1": { corrected: true, at: NOW },
      "B-only": { corrected: false, at: NOW },
    });
  });

  it.each([false, true])("preserves B's marks when A's delayed status says has_voted=%s", async (has_voted) => {
    const response = deferred<{ has_voted: boolean; is_correction: boolean }>();
    const pending = response.promise.then((status) => syncVoteMark("GR-1", status, OWNER, NOW + 1));
    store.data.set("ekklesia_nullifier", OTHER_OWNER);
    await recordVoteMark("GR-1", true, OTHER_OWNER, NOW);
    const before = store.data.get("ekklesia_vote_marks_v1");
    store.setItemAsync.mockClear();

    response.resolve({ has_voted, is_correction: false });
    await pending;

    expect(store.setItemAsync).not.toHaveBeenCalled();
    expect(store.data.get("ekklesia_vote_marks_v1")).toBe(before);
    expect(await loadVoteMarks(NOW + 1)).toEqual({ "GR-1": { corrected: true, at: NOW } });
  });

  it("checks the originating owner when queued updates execute", async () => {
    const marks = { "GR-1": { corrected: true, at: NOW } };
    const before = JSON.stringify({ owner: OTHER_OWNER, marks });
    store.data.set("ekklesia_vote_marks_v1", before);
    // These calls enqueue while A is current; B becomes current before any
    // queued read starts, including the later has_voted=false update.
    const pending = [
      recordVoteMark("A-vote", false, OWNER, NOW + 1),
      recordVoteMark("A-correction", true, OWNER, NOW + 1),
      syncVoteMark("GR-1", { has_voted: true, is_correction: false }, OWNER, NOW + 1),
      syncVoteMark("GR-1", { has_voted: false, is_correction: false }, OWNER, NOW + 1),
    ];
    store.data.set("ekklesia_nullifier", OTHER_OWNER);
    await Promise.all(pending);

    expect(store.setItemAsync).not.toHaveBeenCalled();
    expect(store.data.get("ekklesia_vote_marks_v1")).toBe(before);
    expect(await loadVoteMarks(NOW + 1)).toEqual(marks);
  });

  it.each([null, ""])("rejects an ownerless result (%s) even when a current identity exists", async (expectedOwner) => {
    await recordVoteMark("GR-1", false, OWNER, NOW);
    const before = store.data.get("ekklesia_vote_marks_v1");
    store.setItemAsync.mockClear();

    await recordVoteMark("GR-9", false, expectedOwner, NOW + 1);
    await syncVoteMark("GR-1", { has_voted: false, is_correction: false }, expectedOwner, NOW + 1);

    expect(store.setItemAsync).not.toHaveBeenCalled();
    expect(store.data.get("ekklesia_vote_marks_v1")).toBe(before);
  });

  it("discards results after the current identity is removed", async () => {
    await recordVoteMark("GR-1", false, OWNER, NOW);
    const before = store.data.get("ekklesia_vote_marks_v1");
    store.data.delete("ekklesia_nullifier");
    store.setItemAsync.mockClear();

    await recordVoteMark("GR-9", true, OWNER, NOW + 1);
    await syncVoteMark("GR-1", { has_voted: false, is_correction: false }, OWNER, NOW + 1);

    expect(store.setItemAsync).not.toHaveBeenCalled();
    expect(store.data.get("ekklesia_vote_marks_v1")).toBe(before);
    expect(await loadVoteMarks(NOW + 1)).toEqual({});
  });

  it("keeps the captured owner if identity changes between the read and storage write", async () => {
    store.setItemAsync.mockImplementationOnce(async (key, value) => {
      store.data.set("ekklesia_nullifier", OTHER_OWNER);
      store.data.set(key, value);
    });

    await recordVoteMark("A-vote", false, OWNER, NOW);

    const stored = JSON.parse(store.data.get("ekklesia_vote_marks_v1")!);
    expect(stored.owner).toBe(OWNER);
    expect(stored.marks).toEqual({ "A-vote": { corrected: false, at: NOW } });
    expect(await loadVoteMarks(NOW)).toEqual({});
  });
});

describe("tile vote label", () => {
  beforeEach(() => {
    store.data.clear();
    store.data.set("ekklesia_nullifier", OWNER);
  });

  const mark = (corrected = false) => ({ corrected, at: NOW });

  it("is hidden for unverified users", () => {
    expect(tileVoteLabel("ACTIVE", undefined, false)).toBeNull();
    expect(tileVoteLabel("ACTIVE", mark(), false)).toBeNull();
  });

  it("shows no label without positive evidence (upgrade, other device, web, ZK, expiry)", () => {
    for (const status of ["ACTIVE", "WINDOW_24H", "ANNOUNCED", "PARLIAMENT_VOTED", "OPEN_END"]) {
      expect(tileVoteLabel(status, undefined, true)).toBeNull();
    }
  });

  it("treats an expired or pruned earlier vote as unknown, not as not voted", async () => {
    await recordVoteMark("GR-OLD", false, OWNER, NOW - MAX_AGE_MS - 1);
    const marks = await loadVoteMarks(NOW);
    expect(marks["GR-OLD"]).toBeUndefined();
    expect(tileVoteLabel("ACTIVE", marks["GR-OLD"], true)).toBeNull();
  });

  it("shows voted, correctable in the 24h window, and corrected", () => {
    expect(tileVoteLabel("ACTIVE", mark(), true)).toEqual({ text: "Ψηφίσατε ✓", tone: "done" });
    expect(tileVoteLabel("WINDOW_24H", mark(), true)?.tone).toBe("done");
    expect(tileVoteLabel("WINDOW_24H", { ...mark(), correctable: true }, true)?.tone).toBe("correctable");
    expect(tileVoteLabel("WINDOW_24H", { ...mark(), correctable: false }, true)?.text).toBe("Ψηφίσατε ✓");
    expect(tileVoteLabel("WINDOW_24H", mark(true), true)?.text).toBe("Ψηφίσατε (διορθώθηκε)");
    expect(tileVoteLabel("OPEN_END", mark(), true)?.text).toBe("Ψηφίσατε ✓");
  });
});
