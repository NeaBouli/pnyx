/**
 * Device-local personal vote status for bill tiles (MOBILE-UX-20261007-02).
 *
 * Privacy: only "voted" and "corrected" flags are kept, never the vote choice,
 * and nothing is sent anywhere. The list view does not ask the server per bill
 * (that would link the identity to every listed bill); marks are written after
 * a successful vote/correction and reconciled with the vote-status read the
 * vote screen already performs. Marks are bound to the current nullifier, so a
 * different identity never sees them, and are capped in age and number.
 */
import * as SecureStore from "expo-secure-store";

export interface VoteMark {
  corrected: boolean;
  at: number;
}

export type VoteMarks = Record<string, VoteMark>;

const MARKS_KEY = "ekklesia_vote_marks_v1";
const NULLIFIER_KEY = "ekklesia_nullifier";
export const MAX_MARKS = 150;
export const MAX_AGE_MS = 60 * 24 * 60 * 60 * 1000;

interface Stored {
  owner: string;
  marks: VoteMarks;
}

function prune(marks: VoteMarks, now: number): VoteMarks {
  const fresh = Object.entries(marks).filter(([, m]) => now - m.at <= MAX_AGE_MS);
  fresh.sort((a, b) => b[1].at - a[1].at);
  return Object.fromEntries(fresh.slice(0, MAX_MARKS));
}

async function read(): Promise<{ owner: string | null; marks: VoteMarks }> {
  const [raw, owner] = await Promise.all([
    SecureStore.getItemAsync(MARKS_KEY),
    SecureStore.getItemAsync(NULLIFIER_KEY),
  ]);
  if (!owner) return { owner: null, marks: {} };
  try {
    const parsed = raw ? (JSON.parse(raw) as Stored) : null;
    if (!parsed || parsed.owner !== owner || typeof parsed.marks !== "object") return { owner, marks: {} };
    return { owner, marks: parsed.marks };
  } catch {
    return { owner, marks: {} };
  }
}

async function write(owner: string, marks: VoteMarks, now: number): Promise<void> {
  const stored: Stored = { owner, marks: prune(marks, now) };
  await SecureStore.setItemAsync(MARKS_KEY, JSON.stringify(stored));
}

export async function loadVoteMarks(now: number = Date.now()): Promise<VoteMarks> {
  try {
    const { marks } = await read();
    return prune(marks, now);
  } catch {
    return {};
  }
}

export async function recordVoteMark(billId: string, corrected: boolean, now: number = Date.now()): Promise<void> {
  try {
    const { owner, marks } = await read();
    if (!owner) return;
    marks[billId] = { corrected: corrected || marks[billId]?.corrected === true, at: now };
    await write(owner, marks, now);
  } catch {
    // Display-only state: never block or fail a vote because of it.
  }
}

/** Mirror the server's vote-status read for this bill (has_voted / is_correction). */
export async function syncVoteMark(
  billId: string,
  status: { has_voted: boolean; is_correction: boolean },
  now: number = Date.now(),
): Promise<void> {
  try {
    const { owner, marks } = await read();
    if (!owner) return;
    if (status.has_voted) marks[billId] = { corrected: status.is_correction, at: marks[billId]?.at ?? now };
    else delete marks[billId];
    await write(owner, marks, now);
  } catch {
    // Display-only state.
  }
}

export type TileVoteTone = "done" | "open" | "correctable";

/** Label next to the bill status; never reveals the vote choice. */
export function tileVoteLabel(
  billStatus: string,
  mark: VoteMark | undefined,
  verified: boolean,
): { text: string; tone: TileVoteTone } | null {
  if (!verified) return null;
  if (mark) {
    if (billStatus === "WINDOW_24H" && !mark.corrected) return { text: "Ψηφίσατε · διόρθωση δυνατή", tone: "correctable" };
    if (mark.corrected) return { text: "Ψηφίσατε (διορθώθηκε)", tone: "done" };
    return { text: "Ψηφίσατε ✓", tone: "done" };
  }
  if (billStatus === "ACTIVE" || billStatus === "WINDOW_24H") return { text: "Δεν ψηφίσατε", tone: "open" };
  return null;
}
