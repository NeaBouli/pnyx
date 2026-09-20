/**
 * push-registration.ts — EKA-05 signed Expo push registration.
 *
 * Canonical payload mirrors apps/api/services/push_registration.py exactly:
 *   push-register:v1:<JSON.stringify([device_id, token, platform, nullifier_hash, timestamp_ms])>
 *
 * device_id is a random RFC4122 v4 UUID generated once per install via
 * expo-crypto and persisted in SecureStore — never a device model name.
 * Registration is best-effort and silent: missing identity, network errors
 * and non-signed server responses never throw and never mark success.
 */
import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";
import { ed25519 } from "@noble/curves/ed25519.js";
import { sha256 } from "@noble/hashes/sha2.js";
import { bytesToHex, hexToBytes, loadKeypair, loadNullifier } from "./crypto-native";

const DEVICE_ID_KEY = "push_device_id";
const MARKER_KEY = "push_registration_marker";

/** Refresh well before the server-side 90-day TTL. */
export const PUSH_REGISTRATION_REFRESH_MS = 30 * 24 * 60 * 60 * 1000;

const DEVICE_ID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export type PushPlatform = "android" | "ios";

export type PushRegistrationResult =
  | "registered"   // signed registration accepted (integrity signed-v1)
  | "current"      // fresh marker, no request needed
  | "no-identity"  // no verified keypair/nullifier on device
  | "failed";      // network/server/parse failure — silent, unmarked

interface RegistrationMarker {
  device_id: string;
  token: string;
  platform: string;
  identity_ref: string;
  registered_at: number;
}

export function buildPushRegisterPayload(
  deviceId: string,
  token: string,
  platform: string,
  nullifierHash: string,
  timestampMs: number,
): string {
  if (!Number.isSafeInteger(timestampMs) || timestampMs < 0) {
    throw new Error("Push registration timestamp must be a non-negative safe integer.");
  }
  return `push-register:v1:${JSON.stringify([
    deviceId,
    token,
    platform,
    nullifierHash,
    timestampMs,
  ])}`;
}

/** Random per-install UUID v4, generated once and persisted in SecureStore. */
export async function getOrCreatePushDeviceId(): Promise<string> {
  const stored = await SecureStore.getItemAsync(DEVICE_ID_KEY);
  if (stored && DEVICE_ID_RE.test(stored)) return stored;
  const fresh = Crypto.randomUUID();
  await SecureStore.setItemAsync(DEVICE_ID_KEY, fresh);
  return fresh;
}

function parseMarker(raw: string | null): RegistrationMarker | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<RegistrationMarker>;
    if (
      typeof value.device_id === "string" &&
      typeof value.token === "string" &&
      typeof value.platform === "string" &&
      typeof value.identity_ref === "string" &&
      /^[0-9a-f]{64}$/.test(value.identity_ref) &&
      typeof value.registered_at === "number" &&
      Number.isSafeInteger(value.registered_at) &&
      value.registered_at >= 0
    ) {
      return value as RegistrationMarker;
    }
  } catch {}
  return null;
}

async function readMarker(): Promise<RegistrationMarker | null> {
  try {
    return parseMarker(await SecureStore.getItemAsync(MARKER_KEY));
  } catch {
    return null;
  }
}

async function writeMarker(marker: RegistrationMarker): Promise<void> {
  await SecureStore.setItemAsync(MARKER_KEY, JSON.stringify(marker));
}

function markerIsFresh(
  marker: RegistrationMarker | null,
  deviceId: string,
  token: string,
  platform: string,
  identityRef: string,
  now: number,
): boolean {
  return (
    marker !== null &&
    marker.device_id === deviceId &&
    marker.token === token &&
    marker.platform === platform &&
    marker.identity_ref === identityRef &&
    now >= marker.registered_at &&
    now - marker.registered_at < PUSH_REGISTRATION_REFRESH_MS
  );
}

/**
 * Register the Expo push token with the server when needed.
 *
 * Skips silently without any request when the device has no verified
 * identity, when a fresh marker matches, or on F-Droid (caller gates that).
 * Success is marked only for a 2xx response whose JSON integrity is
 * "signed-v1"; old-server generic 200s and failures stay unmarked so the
 * next launch retries.
 */
export async function registerPushTokenIfNeeded(params: {
  apiBase: string;
  token: string;
  platform: PushPlatform;
  now?: number;
  fetchImpl?: typeof fetch;
}): Promise<PushRegistrationResult> {
  const { apiBase, token, platform } = params;
  const now = params.now ?? Date.now();

  const keypair = await loadKeypair().catch(() => null);
  const nullifierHash = await loadNullifier().catch(() => null);
  if (!keypair || !nullifierHash) return "no-identity";

  try {
    const fetchImpl = params.fetchImpl ?? fetch;
    const deviceId = await getOrCreatePushDeviceId();
    const identityRef = bytesToHex(sha256(
      new TextEncoder().encode(`${keypair.publicKeyHex}:${nullifierHash}`),
    ));
    if (markerIsFresh(
      await readMarker(), deviceId, token, platform, identityRef, now,
    )) {
      return "current";
    }
    const payload = buildPushRegisterPayload(
      deviceId,
      token,
      platform,
      nullifierHash,
      now,
    );
    const signature = ed25519.sign(
      new TextEncoder().encode(payload),
      hexToBytes(keypair.privateKeyHex),
    );
    const response = await fetchImpl(`${apiBase}/api/v1/notify/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token,
        device_id: deviceId,
        platform,
        nullifier_hash: nullifierHash,
        timestamp_ms: now,
        signature_hex: bytesToHex(signature),
      }),
    });
    if (!response.ok) return "failed";
    const body = (await response.json().catch(() => null)) as {
      integrity?: unknown;
    } | null;
    if (!body || body.integrity !== "signed-v1") return "failed";

    await writeMarker({
      device_id: deviceId,
      token,
      platform,
      identity_ref: identityRef,
      registered_at: now,
    });
    return "registered";
  } catch {
    return "failed";
  }
}
