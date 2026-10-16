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
 * Crash safety: the staging slot (bound to nullifier + old key) is the source
 * of truth. If the stored key already (partly) equals the staged key, the swap
 * is finalised locally; if the stored key is still the old key, the staged
 * rotation is re-sent and the server confirms it idempotently. Everything runs
 * under the identity-state lock, so import/verification cannot interleave.
 * The write goes to API_BASE only — never to the read-only mirror.
 */
import { ed25519 } from "@noble/curves/ed25519.js";
import * as Crypto from "expo-crypto";

import {
  bytesToHex,
  clearRotationStaging,
  hexToBytes,
  loadKeyOrigin,
  loadKeypair,
  loadNullifier,
  loadRotationStaging,
  markKeyOriginDevice,
  persistLegacyPolisSeed,
  storeKeypair,
  storeRotationStaging,
  withIdentityStateLock,
  type RotationStaging,
} from "./crypto-native";
import { isDemoMode } from "./demo";

export type RotationResult =
  | "rotated"
  | "already_rotated"
  | "finalized"
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

async function fetchWithTimeout(deps: RotationDeps, url: string, init?: RequestInit): Promise<Response> {
  // The identity lock is held across this call; never let it hang.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), deps.timeoutMs);
  try {
    return await deps.fetchImpl(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function serverSupportsRotation(deps: RotationDeps): Promise<boolean | null> {
  try {
    const res = await fetchWithTimeout(deps, `${deps.apiBase}/api/v1/app/version`);
    if (!res.ok) return null;
    const body = (await res.json()) as { features?: { identity_rotate?: unknown } };
    return body?.features?.identity_rotate === true;
  } catch {
    return null;
  }
}

async function commit(staged: RotationStaging): Promise<void> {
  await storeKeypair(staged.privateKeyHex, staged.publicKeyHex);
  await markKeyOriginDevice(staged.publicKeyHex);
  await clearRotationStaging();
}

async function rotateUnlocked(deps: RotationDeps): Promise<RotationResult> {
  if (await isDemoMode()) return "skipped";

  const current = await loadKeypair();
  const nullifier = await loadNullifier();
  let staged = await loadRotationStaging();

  if (staged && current && staged.nullifier === nullifier) {
    // Interrupted local commit: the stored key already (partly) is the staged key.
    if (current.privateKeyHex === staged.privateKeyHex || current.publicKeyHex === staged.publicKeyHex) {
      await commit(staged);
      return "finalized";
    }
  }
  if (staged && (!current || staged.nullifier !== nullifier || staged.oldPublicKeyHex !== current.publicKeyHex)) {
    // Belongs to credentials that are no longer installed (import, other
    // number, or a server-issued re-verification key): the server key for the
    // installed identity is the installed one, so the staged key is unused.
    await clearRotationStaging();
    staged = null;
  }

  if ((await loadKeyOrigin()) === "device") return "not_needed";
  if (!current || !nullifier) return "skipped";

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

  let res: Response;
  try {
    res = await fetchWithTimeout(deps, `${deps.apiBase}/api/v2/identity/rotate-key`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return "retry_later"; // keep the staged key; the server may or may not have it
  }

  if (res.status === 200) {
    let alreadyRotated = false;
    try {
      alreadyRotated = ((await res.json()) as { already_rotated?: unknown })?.already_rotated === true;
    } catch {
      // body is informational only
    }
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

export function rotateLegacyKeyIfNeeded(deps: RotationDeps = DEFAULT_DEPS): Promise<RotationResult> {
  return withIdentityStateLock(() => rotateUnlocked(deps));
}

let inFlight: Promise<RotationResult> | null = null;
let ranThisSession = false;

/** App-start hook: at most one attempt per app session, never concurrent. */
export function rotateLegacyKeyOnce(): Promise<RotationResult> | null {
  if (ranThisSession) return inFlight;
  ranThisSession = true;
  inFlight = rotateLegacyKeyIfNeeded().catch(() => "retry_later" as const);
  return inFlight;
}

export function resetRotationSessionForTests(): void {
  ranThisSession = false;
  inFlight = null;
}
