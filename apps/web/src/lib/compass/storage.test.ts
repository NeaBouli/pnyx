// @vitest-environment jsdom
import { webcrypto } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createEmptyProfile, seedFromVAA } from "./engine";
import { clearProfile, loadProfile, saveProfile } from "./storage";

const PLAIN = "ekklesia_compass_profile";
const ENCRYPTED = "ekklesia_compass_encrypted";
// Deterministischer Testschlüssel — kein echtes Geheimnis
const KEY = "11".repeat(32);

function sampleProfile() {
  return {
    ...seedFromVAA(createEmptyProfile(), { 1: 1, 2: -1 }, { 1: "Υγεία", 2: "Παιδεία" }),
    selectedModel: "left-right" as const,
  };
}

beforeEach(() => {
  vi.stubGlobal("crypto", webcrypto);
  // jsdom-Realm: nackte ArrayBuffer besteht Nodes WebCrypto-Typprüfung nicht;
  // gleiche Bytes als Uint8Array durchreichen (nur Testumgebung).
  const importKey = webcrypto.subtle.importKey.bind(webcrypto.subtle) as (...args: unknown[]) => Promise<CryptoKey>;
  vi.spyOn(webcrypto.subtle, "importKey").mockImplementation(((format: unknown, keyData: unknown, ...rest: unknown[]) =>
    importKey(format, Object.prototype.toString.call(keyData) === "[object ArrayBuffer]"
      ? new Uint8Array(keyData as ArrayBuffer) : keyData, ...rest)) as typeof webcrypto.subtle.importKey);
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("compass storage — saveProfile fail-closed", () => {
  it("rejects without key and writes neither plaintext nor ciphertext", async () => {
    await expect(saveProfile(sampleProfile(), null)).rejects.toMatchObject({
      name: "CompassStorageError",
      code: "NO_KEY",
    });
    expect(localStorage.getItem(PLAIN)).toBeNull();
    expect(localStorage.getItem(ENCRYPTED)).toBeNull();
  });

  it("rejects on crypto failure without plaintext downgrade", async () => {
    vi.spyOn(webcrypto.subtle, "importKey").mockRejectedValue(new Error("boom"));
    await expect(saveProfile(sampleProfile(), KEY)).rejects.toMatchObject({
      name: "CompassStorageError",
      code: "CRYPTO",
    });
    expect(localStorage.getItem(PLAIN)).toBeNull();
    expect(localStorage.getItem(ENCRYPTED)).toBeNull();
  });

  it("rejects on WebStorage failure without plaintext", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    await expect(saveProfile(sampleProfile(), KEY)).rejects.toMatchObject({
      name: "CompassStorageError",
      code: "STORAGE",
    });
    expect(localStorage.getItem(PLAIN)).toBeNull();
  });

  it("purges legacy plaintext even when a keyless save rejects", async () => {
    localStorage.setItem(PLAIN, JSON.stringify(sampleProfile()));
    await expect(saveProfile(sampleProfile(), null)).rejects.toMatchObject({ code: "NO_KEY" });
    expect(localStorage.getItem(PLAIN)).toBeNull();
  });
});

describe("compass storage — keyed AES-GCM round-trip", () => {
  it("persists only ciphertext and loads it back", async () => {
    const profile = sampleProfile();
    await saveProfile(profile, KEY);
    const stored = localStorage.getItem(ENCRYPTED);
    expect(stored).toBeTruthy();
    expect(stored).not.toContain("left-right");
    expect(localStorage.getItem(PLAIN)).toBeNull();
    await expect(loadProfile(KEY)).resolves.toEqual(profile);
  });

  it("successful ciphertext wins over legacy plaintext and purges it", async () => {
    const profile = sampleProfile();
    await saveProfile(profile, KEY);
    localStorage.setItem(PLAIN, JSON.stringify({ ...createEmptyProfile(), selectedModel: "compass-2d" }));
    await expect(loadProfile(KEY)).resolves.toEqual(profile);
    expect(localStorage.getItem(PLAIN)).toBeNull();
  });

  it("does not fall back to legacy plaintext on decrypt/auth failure", async () => {
    await saveProfile(sampleProfile(), KEY);
    const tampered = localStorage.getItem(ENCRYPTED)!;
    const flipped = (tampered.at(-2) === "A" ? "B" : "A");
    localStorage.setItem(ENCRYPTED, tampered.slice(0, -2) + flipped + tampered.slice(-1));
    const attacker = { ...createEmptyProfile(), selectedModel: "compass-2d" as const };
    localStorage.setItem(PLAIN, JSON.stringify(attacker));

    const loaded = await loadProfile(KEY);
    expect(loaded.selectedModel).toBeNull();
    expect(loaded.signals).toEqual({});
    expect(localStorage.getItem(PLAIN)).toBeNull();
  });
});

describe("compass storage — legacy plaintext migration", () => {
  it("migrates valid legacy with key to ciphertext before returning", async () => {
    const legacy = sampleProfile();
    localStorage.setItem(PLAIN, JSON.stringify(legacy));
    await expect(loadProfile(KEY)).resolves.toEqual(legacy);
    expect(localStorage.getItem(PLAIN)).toBeNull();
    expect(localStorage.getItem(ENCRYPTED)).toBeTruthy();
    await expect(loadProfile(KEY)).resolves.toEqual(legacy);
  });

  it("returns valid legacy without key once in-memory and purges it", async () => {
    const legacy = sampleProfile();
    localStorage.setItem(PLAIN, JSON.stringify(legacy));
    await expect(loadProfile(null)).resolves.toEqual(legacy);
    expect(localStorage.getItem(PLAIN)).toBeNull();
    expect(localStorage.getItem(ENCRYPTED)).toBeNull();
    const second = await loadProfile(null);
    expect(second.selectedModel).toBeNull();
    expect(second.signals).toEqual({});
  });

  it("removes corrupt legacy and returns an empty profile", async () => {
    localStorage.setItem(PLAIN, "{not json");
    const loaded = await loadProfile(KEY);
    expect(loaded.selectedModel).toBeNull();
    expect(loaded.signals).toEqual({});
    expect(localStorage.getItem(PLAIN)).toBeNull();
    expect(localStorage.getItem(ENCRYPTED)).toBeNull();
  });
});

describe("compass storage — clearProfile", () => {
  it("removes both keys", async () => {
    await saveProfile(sampleProfile(), KEY);
    localStorage.setItem(PLAIN, "{}");
    clearProfile();
    expect(localStorage.getItem(PLAIN)).toBeNull();
    expect(localStorage.getItem(ENCRYPTED)).toBeNull();
  });
});
