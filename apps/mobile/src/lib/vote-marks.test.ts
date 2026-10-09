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

describe("tile vote label", () => {
  const mark = (corrected = false) => ({ corrected, at: NOW });

  it("is hidden for unverified users", () => {
    expect(tileVoteLabel("ACTIVE", undefined, false)).toBeNull();
    expect(tileVoteLabel("ACTIVE", mark(), false)).toBeNull();
  });

  it("shows not voted only while voting is open", () => {
    expect(tileVoteLabel("ACTIVE", undefined, true)?.text).toBe("Δεν ψηφίσατε");
    expect(tileVoteLabel("WINDOW_24H", undefined, true)?.tone).toBe("open");
    expect(tileVoteLabel("ANNOUNCED", undefined, true)).toBeNull();
    expect(tileVoteLabel("PARLIAMENT_VOTED", undefined, true)).toBeNull();
  });

  it("shows voted, correctable in the 24h window, and corrected", () => {
    expect(tileVoteLabel("ACTIVE", mark(), true)).toEqual({ text: "Ψηφίσατε ✓", tone: "done" });
    expect(tileVoteLabel("WINDOW_24H", mark(), true)?.tone).toBe("correctable");
    expect(tileVoteLabel("WINDOW_24H", mark(true), true)?.text).toBe("Ψηφίσατε (διορθώθηκε)");
    expect(tileVoteLabel("OPEN_END", mark(), true)?.text).toBe("Ψηφίσατε ✓");
  });
});
