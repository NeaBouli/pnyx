/**
 * EKA-05 signed push registration tests (mock-only, no network).
 *
 * Golden canonical payload values must stay in sync with
 * apps/api/tests/test_notify_register.py.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ed25519 } from "@noble/curves/ed25519.js";
import { sha256 } from "@noble/hashes/sha2.js";

const secureStore = vi.hoisted(() => new Map<string, string>());
const uuidState = vi.hoisted(() => ({
  value: "3f6b1c2e-9a4d-4e5f-8b6c-0d1e2f3a4b5c",
  calls: 0,
}));

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn((key: string) =>
    Promise.resolve(secureStore.get(key) ?? null)),
  setItemAsync: vi.fn((key: string, value: string) => {
    secureStore.set(key, value);
    return Promise.resolve();
  }),
  deleteItemAsync: vi.fn((key: string) => {
    secureStore.delete(key);
    return Promise.resolve();
  }),
}));

vi.mock("expo-crypto", () => ({
  randomUUID: vi.fn(() => {
    uuidState.calls += 1;
    return uuidState.value;
  }),
}));

import {
  buildPushRegisterPayload,
  getOrCreatePushDeviceId,
  PUSH_REGISTRATION_REFRESH_MS,
  registerPushTokenIfNeeded,
} from "./push-registration";
import { bytesToHex, clearKeys } from "./crypto-native";

const API_BASE = "https://api.ekklesia.gr";
const DEVICE_ID = "3f6b1c2e-9a4d-4e5f-8b6c-0d1e2f3a4b5c";
const TOKEN = "ExponentPushToken[abcdefghijklmnopqrstuv]";
const PLATFORM = "android" as const;
const NULLIFIER = "a".repeat(64);
const NOW = 1_788_000_000_000;

const SECRET_KEY = new Uint8Array(32).fill(5);
const PRIVATE_KEY_HEX = Array.from(SECRET_KEY)
  .map((b) => b.toString(16).padStart(2, "0"))
  .join("");
const PUBLIC_KEY = ed25519.getPublicKey(SECRET_KEY);
const PUBLIC_KEY_HEX = bytesToHex(PUBLIC_KEY);
const IDENTITY_REF = bytesToHex(sha256(
  new TextEncoder().encode(`${PUBLIC_KEY_HEX}:${NULLIFIER}`),
));

const GOLDEN_PAYLOAD =
  'push-register:v1:["3f6b1c2e-9a4d-4e5f-8b6c-0d1e2f3a4b5c",' +
  '"ExponentPushToken[abcdefghijklmnopqrstuv]","android",' +
  `"${NULLIFIER}",${NOW}]`;

function seedIdentity(): void {
  secureStore.set("ekklesia_private_key", PRIVATE_KEY_HEX);
  secureStore.set("ekklesia_public_key", PUBLIC_KEY_HEX);
  secureStore.set("ekklesia_nullifier", NULLIFIER);
}

function okResponse(body: unknown): Response {
  return { ok: true, json: async () => body } as Response;
}

function signedMarker(overrides: Record<string, unknown> = {}): string {
  return JSON.stringify({
    device_id: DEVICE_ID,
    token: TOKEN,
    platform: PLATFORM,
    identity_ref: overrides.identity_ref ?? IDENTITY_REF,
    registered_at: NOW,
    ...overrides,
  });
}

beforeEach(() => {
  secureStore.clear();
  uuidState.value = DEVICE_ID;
  uuidState.calls = 0;
});

describe("canonical payload", () => {
  it("matches the cross-client golden vector", () => {
    expect(
      buildPushRegisterPayload(DEVICE_ID, TOKEN, PLATFORM, NULLIFIER, NOW),
    ).toBe(GOLDEN_PAYLOAD);
  });

  it("rejects non-safe timestamps", () => {
    expect(() =>
      buildPushRegisterPayload(DEVICE_ID, TOKEN, PLATFORM, NULLIFIER, -1),
    ).toThrow();
    expect(() =>
      buildPushRegisterPayload(
        DEVICE_ID, TOKEN, PLATFORM, NULLIFIER, Number.MAX_SAFE_INTEGER + 1,
      ),
    ).toThrow();
  });
});

describe("device id persistence", () => {
  it("generates a random UUID once and persists it", async () => {
    const first = await getOrCreatePushDeviceId();
    const second = await getOrCreatePushDeviceId();
    expect(first).toBe(DEVICE_ID);
    expect(second).toBe(DEVICE_ID);
    expect(uuidState.calls).toBe(1);
    expect(secureStore.get("push_device_id")).toBe(DEVICE_ID);
  });

  it("regenerates when the stored value is not a UUID v4", async () => {
    secureStore.set("push_device_id", "android-Pixel-7");
    const fresh = await getOrCreatePushDeviceId();
    expect(fresh).toBe(DEVICE_ID);
    expect(uuidState.calls).toBe(1);
  });
});

describe("signed registration", () => {
  it("posts the exact signed request body", async () => {
    seedIdentity();
    const fetchImpl = vi.fn(async () => okResponse({ registered: true, integrity: "signed-v1" }));
    const result = await registerPushTokenIfNeeded({
      apiBase: API_BASE, token: TOKEN, platform: PLATFORM, now: NOW,
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    expect(result).toBe("registered");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [
      string, { method: string; body: string },
    ];
    expect(url).toBe(`${API_BASE}/api/v1/notify/register`);
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body);
    expect(body).toEqual({
      token: TOKEN,
      device_id: DEVICE_ID,
      platform: PLATFORM,
      nullifier_hash: NULLIFIER,
      timestamp_ms: NOW,
      signature_hex: expect.stringMatching(/^[0-9a-f]{128}$/),
    });
    const payload = buildPushRegisterPayload(
      DEVICE_ID, TOKEN, PLATFORM, NULLIFIER, NOW,
    );
    expect(
      ed25519.verify(
        Uint8Array.from(
          (body.signature_hex.match(/../g) as string[]).map((h) => parseInt(h, 16)),
        ),
        new TextEncoder().encode(payload),
        PUBLIC_KEY,
      ),
    ).toBe(true);
  });

  it("skips silently without a verified keypair or nullifier", async () => {
    const fetchImpl = vi.fn();
    await expect(
      registerPushTokenIfNeeded({
        apiBase: API_BASE, token: TOKEN, platform: PLATFORM, now: NOW,
        fetchImpl: fetchImpl as unknown as typeof fetch,
      }),
    ).resolves.toBe("no-identity");

    secureStore.set("ekklesia_private_key", PRIVATE_KEY_HEX);
    secureStore.set("ekklesia_public_key", "ab".repeat(32));
    await expect(
      registerPushTokenIfNeeded({
        apiBase: API_BASE, token: TOKEN, platform: PLATFORM, now: NOW,
        fetchImpl: fetchImpl as unknown as typeof fetch,
      }),
    ).resolves.toBe("no-identity");
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("marks success only for a signed-v1 response and then stays current", async () => {
    seedIdentity();
    const fetchImpl = vi.fn(async () => okResponse({ registered: true, integrity: "signed-v1" }));
    const params = {
      apiBase: API_BASE, token: TOKEN, platform: PLATFORM, now: NOW,
      fetchImpl: fetchImpl as unknown as typeof fetch,
    };
    await expect(registerPushTokenIfNeeded(params)).resolves.toBe("registered");
    expect(JSON.parse(secureStore.get("push_registration_marker") as string))
      .toEqual({
        device_id: DEVICE_ID, token: TOKEN, platform: PLATFORM,
        identity_ref: IDENTITY_REF,
        registered_at: NOW,
      });
    // A second call within the refresh window makes no request.
    await expect(registerPushTokenIfNeeded(params)).resolves.toBe("current");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["old-server generic 200", okResponse({ registered: true })],
    ["non-2xx response", { ok: false, status: 401, json: async () => ({}) } as Response],
    ["malformed JSON body", { ok: true, json: async () => { throw new Error("bad"); } } as unknown as Response],
  ])("does not mark success on %s", async (_label, response) => {
    seedIdentity();
    const fetchImpl = vi.fn(async () => response);
    await expect(
      registerPushTokenIfNeeded({
        apiBase: API_BASE, token: TOKEN, platform: PLATFORM, now: NOW,
        fetchImpl: fetchImpl as unknown as typeof fetch,
      }),
    ).resolves.toBe("failed");
    expect(secureStore.get("push_registration_marker")).toBeUndefined();
  });

  it("stays silent and unmarked on network errors", async () => {
    seedIdentity();
    const fetchImpl = vi.fn(async () => { throw new Error("offline"); });
    await expect(
      registerPushTokenIfNeeded({
        apiBase: API_BASE, token: TOKEN, platform: PLATFORM, now: NOW,
        fetchImpl: fetchImpl as unknown as typeof fetch,
      }),
    ).resolves.toBe("failed");
    expect(secureStore.get("push_registration_marker")).toBeUndefined();
  });
});

describe("30-day registration marker", () => {
  const fetchOk = () =>
    vi.fn(async () => okResponse({ registered: true, integrity: "signed-v1" }));

  async function attempt(now: number, token = TOKEN) {
    const fetchImpl = fetchOk();
    const result = await registerPushTokenIfNeeded({
      apiBase: API_BASE, token, platform: PLATFORM, now,
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    return { result, calls: fetchImpl.mock.calls.length };
  }

  it("reposts only when stale, changed, or malformed", async () => {
    seedIdentity();

    // Fresh marker: no request.
    secureStore.set("push_registration_marker", signedMarker());
    expect(await attempt(NOW + 1_000)).toEqual({ result: "current", calls: 0 });

    // One ms before the 30-day boundary: still current.
    secureStore.set("push_registration_marker", signedMarker());
    expect(await attempt(NOW + PUSH_REGISTRATION_REFRESH_MS - 1))
      .toEqual({ result: "current", calls: 0 });

    // Older than 30 days: repost.
    secureStore.set("push_registration_marker", signedMarker());
    expect(await attempt(NOW + PUSH_REGISTRATION_REFRESH_MS + 1))
      .toEqual({ result: "registered", calls: 1 });

    // Token change: repost.
    secureStore.set("push_registration_marker", signedMarker());
    expect(await attempt(NOW + 2_000, "ExpoPushToken[xxxxxxxxxxxxxx]"))
      .toEqual({ result: "registered", calls: 1 });

    // Device change: repost.
    secureStore.set("push_registration_marker", signedMarker({
      device_id: "11111111-2222-4333-8444-555555555555",
    }));
    expect(await attempt(NOW + 3_000)).toEqual({ result: "registered", calls: 1 });

    // Malformed marker: repost.
    secureStore.set("push_registration_marker", "{not json");
    expect(await attempt(NOW + 4_000)).toEqual({ result: "registered", calls: 1 });

    // Marker with wrong shape: repost.
    secureStore.set("push_registration_marker", JSON.stringify({
      device_id: DEVICE_ID, token: TOKEN,
    }));
    expect(await attempt(NOW + 5_000)).toEqual({ result: "registered", calls: 1 });
  });

  it("reposts after the verified identity changes", async () => {
    seedIdentity();
    const fetchImpl = fetchOk();
    const params = {
      apiBase: API_BASE,
      token: TOKEN,
      platform: PLATFORM,
      fetchImpl: fetchImpl as unknown as typeof fetch,
    };

    await expect(registerPushTokenIfNeeded({ ...params, now: NOW }))
      .resolves.toBe("registered");
    const firstMarker = JSON.parse(
      secureStore.get("push_registration_marker") as string,
    );

    const rotatedSecret = new Uint8Array(32).fill(9);
    secureStore.set("ekklesia_private_key", bytesToHex(rotatedSecret));
    secureStore.set(
      "ekklesia_public_key",
      bytesToHex(ed25519.getPublicKey(rotatedSecret)),
    );
    secureStore.set("ekklesia_nullifier", "b".repeat(64));

    await expect(registerPushTokenIfNeeded({ ...params, now: NOW + 1_000 }))
      .resolves.toBe("registered");
    const rotatedMarker = JSON.parse(
      secureStore.get("push_registration_marker") as string,
    );
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(rotatedMarker.identity_ref).not.toBe(firstMarker.identity_ref);
  });

  it("removes the registration marker when identity keys are cleared", async () => {
    seedIdentity();
    secureStore.set("push_device_id", DEVICE_ID);
    secureStore.set("push_registration_marker", signedMarker());

    await clearKeys();

    expect(secureStore.get("push_registration_marker")).toBeUndefined();
    expect(secureStore.get("push_device_id")).toBe(DEVICE_ID);
  });
});
