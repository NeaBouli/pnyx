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

import { MAX_AGE_MS, MAX_MARKS, loadVoteMarks, recordVoteMark, syncVoteMark, tileVoteLabel } from "./vote-marks";

const OWNER = "a".repeat(64);
const NOW = 1_800_000_000_000;

describe("vote marks storage", () => {
  beforeEach(() => {
    store.data.clear();
    store.data.set("ekklesia_nullifier", OWNER);
  });

  it("records a vote without the choice and reads it back", async () => {
    await recordVoteMark("GR-1", false, NOW);
    expect(await loadVoteMarks(NOW)).toEqual({ "GR-1": { corrected: false, at: NOW } });
    const raw = store.data.get("ekklesia_vote_marks_v1")!;
    expect(raw).not.toMatch(/YES|NO|ABSTAIN|vote"/);
  });

  it("keeps the corrected flag once set", async () => {
    await recordVoteMark("GR-1", true, NOW);
    await recordVoteMark("GR-1", false, NOW + 1);
    expect((await loadVoteMarks(NOW + 1))["GR-1"].corrected).toBe(true);
  });

  it("syncs with the server status and removes stale marks", async () => {
    await syncVoteMark("GR-2", { has_voted: true, is_correction: true }, NOW);
    expect((await loadVoteMarks(NOW))["GR-2"]).toEqual({ corrected: true, at: NOW });
    await syncVoteMark("GR-2", { has_voted: false, is_correction: false }, NOW);
    expect(await loadVoteMarks(NOW)).toEqual({});
  });

  it("ignores marks of a different identity and stores nothing without one", async () => {
    await recordVoteMark("GR-1", false, NOW);
    store.data.set("ekklesia_nullifier", "b".repeat(64));
    expect(await loadVoteMarks(NOW)).toEqual({});
    store.data.delete("ekklesia_nullifier");
    await recordVoteMark("GR-9", false, NOW);
    expect(await loadVoteMarks(NOW)).toEqual({});
  });

  it("prunes by age and count", async () => {
    await recordVoteMark("OLD", false, NOW - MAX_AGE_MS - 1);
    for (let i = 0; i < MAX_MARKS + 5; i++) await recordVoteMark(`B-${i}`, false, NOW + i);
    const marks = await loadVoteMarks(NOW + MAX_MARKS + 5);
    expect(Object.keys(marks)).toHaveLength(MAX_MARKS);
    expect(marks.OLD).toBeUndefined();
    expect(marks["B-0"]).toBeUndefined();
  });

  it("never throws on corrupt storage", async () => {
    store.data.set("ekklesia_vote_marks_v1", "{not json");
    expect(await loadVoteMarks(NOW)).toEqual({});
    await expect(recordVoteMark("GR-1", false, NOW)).resolves.toBeUndefined();
  });
});

describe("vote marks follow-ups (#487 review)", () => {
  beforeEach(() => {
    store.data.clear();
    store.data.set("ekklesia_nullifier", OWNER);
  });

  it("stores the server's can_correct and refreshes the timestamp on sync", async () => {
    await recordVoteMark("GR-5", false, NOW - 1000);
    await syncVoteMark("GR-5", { has_voted: true, is_correction: false, can_correct: true }, NOW);
    expect((await loadVoteMarks(NOW))["GR-5"]).toEqual({ corrected: false, at: NOW, correctable: true });
  });

  it("a later local vote makes correctability unknown again", async () => {
    await syncVoteMark("GR-6", { has_voted: true, is_correction: false, can_correct: true }, NOW);
    await recordVoteMark("GR-6", true, NOW + 1);
    expect((await loadVoteMarks(NOW + 1))["GR-6"].correctable).toBeUndefined();
  });

  it("concurrent updates do not overwrite each other", async () => {
    await Promise.all([
      recordVoteMark("A", false, NOW),
      syncVoteMark("B", { has_voted: true, is_correction: false, can_correct: false }, NOW),
      recordVoteMark("C", true, NOW),
      recordVoteMark("D", false, NOW),
      syncVoteMark("E", { has_voted: true, is_correction: true }, NOW),
    ]);
    expect(Object.keys(await loadVoteMarks(NOW)).sort()).toEqual(["A", "B", "C", "D", "E"]);
  });
});

describe("tile vote label", () => {
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
    await recordVoteMark("GR-OLD", false, NOW - MAX_AGE_MS - 1);
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
