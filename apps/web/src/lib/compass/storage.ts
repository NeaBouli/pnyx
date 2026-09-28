/**
 * Compass Storage — Verschlüsselte Speicherung des Kompass-Profils.
 * Verwendet AES-256-GCM abgeleitet vom Ed25519 Private Key via HKDF.
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
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw === null) return null;
  localStorage.removeItem(STORAGE_KEY);
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
export async function loadProfile(privateKeyHex: string | null): Promise<CompassProfile> {
  if (typeof window === "undefined") return createEmptyProfile();

  const legacy = takeLegacyProfile();
  const encrypted = localStorage.getItem(STORAGE_KEY_ENCRYPTED);

  if (encrypted) {
    if (privateKeyHex) {
      try {
        const key = await deriveAesKey(privateKeyHex);
        const json = await decrypt(encrypted, key);
        return JSON.parse(json) as CompassProfile;
      } catch {
        // Entschlüsselung fehlgeschlagen — kein Rückfall auf Klartext
      }
    }
    return createEmptyProfile();
  }

  if (!legacy) return createEmptyProfile();

  if (privateKeyHex) {
    try {
      await saveProfile(legacy, privateKeyHex);
    } catch {
      // Migration fehlgeschlagen — Profil bleibt nur in-memory
    }
  }
  return legacy;
}

/** Speichert das Kompass-Profil ausschließlich verschlüsselt. Ohne Key oder bei Fehler: reject. */
export async function saveProfile(profile: CompassProfile, privateKeyHex: string | null): Promise<void> {
  if (typeof window === "undefined") return;

  withStorage(() => localStorage.removeItem(STORAGE_KEY));

  if (!privateKeyHex) {
    throw new CompassStorageError("NO_KEY", "Compass profile requires a key to be stored");
  }

  let encrypted: string;
  try {
    const key = await deriveAesKey(privateKeyHex);
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
