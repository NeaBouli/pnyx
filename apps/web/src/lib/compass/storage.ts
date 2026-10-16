/**
 * Compass Storage — Verschlüsselte Speicherung des Kompass-Profils.
 * Verwendet AES-256-GCM: seit EVA-003 mit einem eigenen, nicht extrahierbaren
 * Schlüssel aus IndexedDB; Legacy: abgeleitet vom Ed25519 Private Key via HKDF.
 * Kein Klartext-Fallback: ohne Key oder bei Fehler wird nichts persistiert.
 */
import type { CompassProfile } from "./types";
import { createEmptyProfile } from "./engine";

const STORAGE_KEY = "ekklesia_compass_profile";
const STORAGE_KEY_ENCRYPTED = "ekklesia_compass_encrypted";
const HKDF_SALT = new TextEncoder().encode("ekklesia-compass-v1");
const HKDF_INFO = new TextEncoder().encode("aes-256-gcm");

// ─── Krypto-Hilfsfunktionen ─────────────────────────────────────────────────

function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return bytes;
}

async function deriveAesKey(privateKeyHex: string): Promise<CryptoKey> {
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    hexToBytes(privateKeyHex).buffer as ArrayBuffer,
    "HKDF",
    false,
    ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    { name: "HKDF", hash: "SHA-256", salt: HKDF_SALT, info: HKDF_INFO },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

async function encrypt(data: string, key: CryptoKey): Promise<string> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    new TextEncoder().encode(data)
  );
  const combined = new Uint8Array(iv.length + encrypted.byteLength);
  combined.set(iv);
  combined.set(new Uint8Array(encrypted), iv.length);
  return btoa(String.fromCharCode(...combined));
}

async function decrypt(base64: string, key: CryptoKey): Promise<string> {
  const combined = Uint8Array.from(atob(base64), c => c.charCodeAt(0));
  const iv = combined.slice(0, 12);
  const ciphertext = combined.slice(12);
  const decrypted = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv },
    key,
    ciphertext
  );
  return new TextDecoder().decode(decrypted);
}

// ─── Schlüsselquellen ───────────────────────────────────────────────────────

/**
 * EVA-003: aesKey = non-extractable Compass key (IndexedDB); legacyPrivateKeyHex
 * = plaintext identity key of not yet migrated browsers. A plain string is the
 * legacy key (backwards compatible call sites).
 */
export interface CompassKeys {
  aesKey?: CryptoKey | null;
  legacyPrivateKeyHex?: string | null;
}

function normalizeKeys(keys: string | CompassKeys | null): CompassKeys {
  if (keys === null) return {};
  return typeof keys === "string" ? { legacyPrivateKeyHex: keys } : keys;
}

async function encryptionKey(keys: CompassKeys): Promise<CryptoKey | null> {
  if (keys.aesKey) return keys.aesKey;
  if (keys.legacyPrivateKeyHex) return deriveAesKey(keys.legacyPrivateKeyHex);
  return null;
}

async function decryptWithAny(blob: string, keys: CompassKeys): Promise<string | null> {
  if (keys.aesKey) {
    try {
      return await decrypt(blob, keys.aesKey);
    } catch {
      // not (yet) encrypted with the new key
    }
  }
  if (keys.legacyPrivateKeyHex) {
    try {
      return await decrypt(blob, await deriveAesKey(keys.legacyPrivateKeyHex));
    } catch {
      // wrong or no legacy key
    }
  }
  return null;
}

function isStructurallyValidBlob(blob: string): boolean {
  try {
    return atob(blob).length >= 12 + 16; // IV + GCM tag at minimum
  } catch {
    return false;
  }
}

/**
 * EVA-003 migration step: move the stored ciphertext from the legacy
 * HKDF key to the new key. Idempotent. Returns false only if the blob is
 * readable with the legacy key but could not be re-encrypted/stored, so the
 * caller keeps the legacy key. An absent or already migrated blob returns
 * true; so does a STRUCTURALLY broken blob (not base64 / shorter than IV+tag),
 * which no key can ever read. A failed AES-GCM decrypt is ambiguous (wrong key
 * or transient error) and returns false, so the legacy key is kept for retry.
 */
export async function reencryptLegacyCompassBlob(legacyPrivateKeyHex: string, aesKey: CryptoKey): Promise<boolean> {
  let blob: string | null;
  try {
    blob = localStorage.getItem(STORAGE_KEY_ENCRYPTED);
  } catch {
    return false;
  }
  if (!blob) return true;
  try {
    await decrypt(blob, aesKey);
    return true; // already migrated
  } catch {
    // continue with the legacy key
  }
  let legacyKey: CryptoKey;
  try {
    legacyKey = await deriveAesKey(legacyPrivateKeyHex);
  } catch {
    return false; // operational crypto failure: keep the legacy key and retry
  }
  if (!isStructurallyValidBlob(blob)) return true; // corrupt: unreadable with any key
  let json: string;
  try {
    json = await decrypt(blob, legacyKey);
  } catch {
    return false; // ambiguous decrypt failure: keep the legacy key and retry
  }
  try {
    const next = await encrypt(json, aesKey);
    if ((await decrypt(next, aesKey)) !== json) return false;
    localStorage.setItem(STORAGE_KEY_ENCRYPTED, next);
    return true;
  } catch {
    return false;
  }
}

// ─── Öffentliche API ────────────────────────────────────────────────────────

export type CompassStorageErrorCode = "NO_KEY" | "CRYPTO" | "STORAGE";

/** Speichern fehlgeschlagen — es wurde nichts als Klartext persistiert. */
export class CompassStorageError extends Error {
  readonly code: CompassStorageErrorCode;

  constructor(code: CompassStorageErrorCode, message: string, cause?: unknown) {
    super(message, { cause });
    this.name = "CompassStorageError";
    this.code = code;
  }
}

function withStorage(action: () => void): void {
  try {
    action();
  } catch (cause) {
    throw new CompassStorageError("STORAGE", "Compass profile storage unavailable", cause);
  }
}

/** Liest Legacy-Klartext und entfernt ihn sofort aus dem persistenten Storage. */
function takeLegacyProfile(): CompassProfile | null {
  let raw: string | null;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
    if (raw === null) return null;
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    return null; // Storage nicht verfügbar: kein Profil, kein Klartext-Rückfall
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? (parsed as CompassProfile)
      : null;
  } catch {
    return null; // Korrupt — verworfen
  }
}

/**
 * Lädt das Kompass-Profil. Ciphertext hat Vorrang; Legacy-Klartext wird nur
 * ohne Ciphertext übernommen, sofort gelöscht und mit Key verschlüsselt migriert.
 */
export async function loadProfile(keysOrPrivateKeyHex: string | CompassKeys | null): Promise<CompassProfile> {
  if (typeof window === "undefined") return createEmptyProfile();
  const keys = normalizeKeys(keysOrPrivateKeyHex);

  const legacy = takeLegacyProfile();
  let encrypted: string | null;
  try {
    encrypted = localStorage.getItem(STORAGE_KEY_ENCRYPTED);
  } catch {
    return createEmptyProfile(); // Storage nicht verfügbar — kein Klartext-Rückfall
  }

  if (encrypted) {
    const json = await decryptWithAny(encrypted, keys);
    if (json !== null) {
      try {
        return JSON.parse(json) as CompassProfile;
      } catch {
        // korrupt — kein Rückfall auf Klartext
      }
    }
    return createEmptyProfile();
  }

  if (!legacy) return createEmptyProfile();

  if (keys.aesKey || keys.legacyPrivateKeyHex) {
    try {
      await saveProfile(legacy, keys);
    } catch {
      // Migration fehlgeschlagen — Profil bleibt nur in-memory
    }
  }
  return legacy;
}

/** Speichert das Kompass-Profil ausschließlich verschlüsselt. Ohne Key oder bei Fehler: reject. */
export async function saveProfile(profile: CompassProfile, keysOrPrivateKeyHex: string | CompassKeys | null): Promise<void> {
  if (typeof window === "undefined") return;
  const keys = normalizeKeys(keysOrPrivateKeyHex);

  withStorage(() => localStorage.removeItem(STORAGE_KEY));

  if (!keys.aesKey && !keys.legacyPrivateKeyHex) {
    throw new CompassStorageError("NO_KEY", "Compass profile requires a key to be stored");
  }

  let encrypted: string;
  try {
    const key = (await encryptionKey(keys))!;
    encrypted = await encrypt(JSON.stringify(profile), key);
  } catch (cause) {
    throw new CompassStorageError("CRYPTO", "Compass profile encryption failed", cause);
  }

  withStorage(() => localStorage.setItem(STORAGE_KEY_ENCRYPTED, encrypted));
}

/** Löscht das Kompass-Profil vollständig */
export function clearProfile(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(STORAGE_KEY_ENCRYPTED);
}
