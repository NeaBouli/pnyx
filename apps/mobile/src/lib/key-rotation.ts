/**
 * EVA-001 PR4 — rotate a legacy server-generated identity key to a key that
 * was generated on this device.
 *
 * Runs once per app session in the background and only when the server
 * advertises `features.identity_rotate` in GET /api/v1/app/version.
 *
 *   1. Persist the legacy POLIS seed (pk_polis must survive the swap).
 *   2. Generate the new key and keep it in a staging slot.
 *   3. POST /api/v2/identity/rotate-key, signed by the old AND the new key.
 *   4. On 200 commit the new key, mark the origin "device", drop the staging.
 *
 * Crash safety: the local commit is one journaled write (key pair + marker +
 * staging removal), rolled forward after an interruption. Before the commit,
 * the staging slot (bound to nullifier + old key) holds the new key; while the
 * stored key is still the old one the staged rotation is re-sent and the
 * server confirms it idempotently. Runs under the identity-state lock, only
 * when no verification/import holds or waits for it.
 * The write goes to API_BASE only — never to the read-only mirror.
 */
import { ed25519 } from "@noble/curves/ed25519.js";
import * as Crypto from "expo-crypto";

import {
  IDENTITY_STORE_KEYS,
  bytesToHex,
  clearRotationStaging,
  hexToBytes,
  installIdentityState,
  hasPendingIdentityJournal,
  isConsistentKeypair,
  loadKeyOrigin,
  loadKeypairRaw,
  loadNullifier,
  loadRotationStaging,
  persistLegacyPolisSeed,
  storeRotationStaging,
  tryWithIdentityStateLock,
  withIdentityStateLock,
  type RotationStaging,
} from "./crypto-native";
import { isDemoMode } from "./demo";

export type RotationResult =
  | "rotated"
  | "already_rotated"
  | "not_needed"
  | "skipped"
  | "unsupported"
  | "conflict"
  | "retry_later";

export interface RotationDeps {
  apiBase: string;
  fetchImpl: typeof fetch;
  randomBytes: (length: number) => Uint8Array;
  now: () => number;
  timeoutMs: number;
}

const DEFAULT_DEPS: RotationDeps = {
  apiBase: process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr",
  fetchImpl: (...args) => fetch(...args),
  randomBytes: (length) => Crypto.getRandomBytes(length),
  now: () => Date.now(),
  timeoutMs: 15_000,
};

export function identityRotateMessage(
  nullifierHash: string,
  oldPublicKeyHex: string,
  newPublicKeyHex: string,
  timestampMs: number,
): string {
  // Must match apps/api/routers/identity.py::identity_rotate_message.
  return `ekklesia:identity-rotate:v1:${nullifierHash}:${oldPublicKeyHex}:${newPublicKeyHex}:${timestampMs}`;
}

async function fetchJsonWithTimeout(
  deps: RotationDeps,
  url: string,
  init?: RequestInit,
): Promise<{ status: number; body: unknown }> {
  // The identity lock is held across this call: the deadline covers the
  // headers AND the body, so a stalled response cannot hold the lock.
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new Error("timeout"));
    }, deps.timeoutMs);
  });
  try {
    return await Promise.race([
      (async () => {
        const res = await deps.fetchImpl(url, { ...init, signal: controller.signal });
        const text = await res.text();
        let body: unknown = null;
        try {
          body = text ? JSON.parse(text) : null;
        } catch {
          body = null;
        }
        return { status: res.status, body };
      })(),
      deadline,
    ]);
  } finally {
    clearTimeout(timer);
  }
}

async function serverSupportsRotation(deps: RotationDeps): Promise<boolean | null> {
  try {
    const res = await fetchJsonWithTimeout(deps, `${deps.apiBase}/api/v1/app/version`);
    if (res.status !== 200) return null;
    const body = res.body as { features?: { identity_rotate?: unknown } } | null;
    return body?.features?.identity_rotate === true;
  } catch {
    return null;
  }
}

async function commit(staged: RotationStaging): Promise<void> {
  // One journaled unit: no mixed key pair, marker or staging can survive a crash.
  await installIdentityState({
    [IDENTITY_STORE_KEYS.privateKey]: staged.privateKeyHex,
    [IDENTITY_STORE_KEYS.publicKey]: staged.publicKeyHex,
    [IDENTITY_STORE_KEYS.keyOrigin]: staged.publicKeyHex,
    [IDENTITY_STORE_KEYS.rotationStaging]: null,
  });
}

async function rotateUnlocked(deps: RotationDeps): Promise<RotationResult> {
  if (await isDemoMode()) return "skipped";

  // The lock already rolled any interrupted journal forward: the stored
  // credentials are complete and authoritative here.
  if (await hasPendingIdentityJournal()) return "skipped"; // unreadable journal: never act destructively
  const current = await loadKeypairRaw();
  const nullifier = await loadNullifier();
  if (!current || !nullifier) return "skipped";
  if (!isConsistentKeypair(current)) return "skipped"; // never rotate or mark a broken pair

  let staged = await loadRotationStaging();
  if (staged && (staged.nullifier !== nullifier || staged.oldPublicKeyHex !== current.publicKeyHex)) {
    // The installed credentials are complete (journal) and were deliberately
    // replaced since this staging was written: another identity (import /
    // verification of another number, which replaced that identity on this
    // device), or a key the server issued/holds for this identity (v1
    // re-verification, import). The staged key is not the installed
    // identity's server key, so it is obsolete.
    await clearRotationStaging();
    staged = null;
  }

  if ((await loadKeyOrigin()) === "device") return "not_needed";

  const supported = await serverSupportsRotation(deps);
  if (supported === null) return "retry_later";
  if (!supported) return "unsupported";

  if (!staged) {
    await persistLegacyPolisSeed();
    const seed = deps.randomBytes(32);
    if (!(seed instanceof Uint8Array) || seed.length !== 32) return "retry_later";
    staged = {
      nullifier,
      oldPublicKeyHex: current.publicKeyHex,
      privateKeyHex: bytesToHex(seed),
      publicKeyHex: bytesToHex(ed25519.getPublicKey(seed)),
    };
    await storeRotationStaging(staged);
  }

  const timestampMs = deps.now();
  const message = new TextEncoder().encode(
    identityRotateMessage(nullifier, current.publicKeyHex, staged.publicKeyHex, timestampMs),
  );
  const body = {
    nullifier_hash: nullifier,
    old_public_key_hex: current.publicKeyHex,
    new_public_key_hex: staged.publicKeyHex,
    timestamp_ms: timestampMs,
    old_signature_hex: bytesToHex(ed25519.sign(message, hexToBytes(current.privateKeyHex))),
    new_signature_hex: bytesToHex(ed25519.sign(message, hexToBytes(staged.privateKeyHex))),
  };

  let res: { status: number; body: unknown };
  try {
    res = await fetchJsonWithTimeout(deps, `${deps.apiBase}/api/v2/identity/rotate-key`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return "retry_later"; // keep the staged key; the server may or may not have it
  }

  if (res.status === 200) {
    const alreadyRotated = (res.body as { already_rotated?: unknown } | null)?.already_rotated === true;
    await commit(staged);
    return alreadyRotated ? "already_rotated" : "rotated";
  }
  if (res.status === 409) {
    // The server holds neither the old+new pair nor the new key (an identical
    // retry would have been confirmed with 200), so the staged key is unused.
    await clearRotationStaging();
    return "conflict";
  }
  // 400 (e.g. clock skew), 404 (flag switched off), 429, 5xx: an earlier,
  // interrupted attempt may already have moved the server to the staged key,
  // so it is kept and re-sent next session.
  return res.status === 404 ? "unsupported" : "retry_later";
}

export async function rotateLegacyKeyIfNeeded(deps: RotationDeps = DEFAULT_DEPS): Promise<RotationResult> {
  // Background work: never queue behind (or block) verification/import.
  const run = tryWithIdentityStateLock(() => rotateUnlocked(deps));
  return run ?? "retry_later";
}

let inFlight: Promise<RotationResult> | null = null;
let lastResult: RotationResult | null = null;
let lastAttemptAt = 0;
export const ROTATION_RETRY_INTERVAL_MS = 60_000;

/**
 * App start / foreground hook. Never concurrent. A final outcome is not
 * retried within the session; "retry_later" (lost response, offline, server
 * busy, lock busy) is retried on the next foreground event after at most
 * ROTATION_RETRY_INTERVAL_MS, so an applied-but-unconfirmed rotation is
 * recovered as soon as the network is back, without a process restart.
 */
export function maybeRotateLegacyKey(now: number = Date.now()): Promise<RotationResult> | null {
  if (inFlight) return inFlight;
  if (lastResult !== null && lastResult !== "retry_later") return null;
  if (lastResult === "retry_later" && now - lastAttemptAt < ROTATION_RETRY_INTERVAL_MS) return null;
  lastAttemptAt = now;
  inFlight = withIdentityStateLock(async () => undefined) // rolls an interrupted journal forward
    .then(() => rotateLegacyKeyIfNeeded())
    .catch(() => "retry_later" as const)
    .then((result) => {
      lastResult = result;
      inFlight = null;
      return result;
    });
  return inFlight;
}

export function resetRotationSessionForTests(): void {
  inFlight = null;
  lastResult = null;
  lastAttemptAt = 0;
}
