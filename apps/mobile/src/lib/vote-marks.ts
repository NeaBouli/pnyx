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
  /** Server's can_correct from the last vote-status read; absent = unknown. */
  correctable?: boolean;
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

// All read-modify-write updates run one after another, so concurrent calls
// (vote + status read, double taps) cannot overwrite each other's marks.
let queue: Promise<void> = Promise.resolve();
function serialized(update: () => Promise<void>): Promise<void> {
  const next = queue.then(update, update);
  queue = next.catch(() => {});
  return queue;
}

export function recordVoteMark(billId: string, corrected: boolean, now: number = Date.now()): Promise<void> {
  return serialized(async () => {
    try {
      const { owner, marks } = await read();
      if (!owner) return;
      const previous = marks[billId];
      // A fresh local vote/correction: whether it can still be corrected is
      // unknown until the next server status read.
      marks[billId] = { corrected: corrected || previous?.corrected === true, at: now };
      await write(owner, marks, now);
    } catch {
      // Display-only state: never block or fail a vote because of it.
    }
  });
}

/** Mirror the server's vote-status read for this bill (has_voted / is_correction / can_correct). */
export function syncVoteMark(
  billId: string,
  status: { has_voted: boolean; is_correction: boolean; can_correct?: boolean },
  now: number = Date.now(),
): Promise<void> {
  return serialized(async () => {
    try {
      const { owner, marks } = await read();
      if (!owner) return;
      if (status.has_voted) {
        marks[billId] = {
          corrected: status.is_correction,
          at: now,
          ...(typeof status.can_correct === "boolean" ? { correctable: status.can_correct } : {}),
        };
      } else {
        delete marks[billId];
      }
      await write(owner, marks, now);
    } catch {
      // Display-only state.
    }
  });
}

export type TileVoteTone = "done" | "correctable";

/**
 * Label next to the bill status; never reveals the vote choice. Shown only for
 * positive device-local evidence of a vote; unknown stays without a label.
 */
export function tileVoteLabel(
  billStatus: string,
  mark: VoteMark | undefined,
  verified: boolean,
): { text: string; tone: TileVoteTone } | null {
  if (!verified) return null;
  if (mark) {
    // Only the server knows correction rules (24h window, single correction,
    // ZK tier lock); claim "correctable" only from its can_correct.
    if (billStatus === "WINDOW_24H" && !mark.corrected && mark.correctable === true) {
      return { text: "Ψηφίσατε · διόρθωση δυνατή", tone: "correctable" };
    }
    if (mark.corrected) return { text: "Ψηφίσατε (διορθώθηκε)", tone: "done" };
    return { text: "Ψηφίσατε ✓", tone: "done" };
  }
  // No mark is no proof of "not voted": the cache is lossy by design (upgrade,
  // other device, web, ZK, expiry, storage errors). Only positive evidence is shown.
  return null;
}
