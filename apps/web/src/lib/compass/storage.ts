/**
 * Compass Storage — Verschlüsselte Speicherung des Kompass-Profils.
 * Verwendet AES-256-GCM abgeleitet vom Ed25519 Private Key via HKDF.
 * Fallback auf unverschlüsselt wenn kein Key vorhanden.
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

/** Lädt das Kompass-Profil. Versucht verschlüsselt, dann unverschlüsselt. */
export async function loadProfile(privateKeyHex: string | null): Promise<CompassProfile> {
  if (typeof window === "undefined") return createEmptyProfile();

  // Verschlüsselt laden
  if (privateKeyHex) {
    const encrypted = localStorage.getItem(STORAGE_KEY_ENCRYPTED);
    if (encrypted) {
      try {
        const key = await deriveAesKey(privateKeyHex);
        const json = await decrypt(encrypted, key);
        return JSON.parse(json) as CompassProfile;
      } catch {
        // Entschlüsselung fehlgeschlagen — neues Profil
      }
    }
  }

  // Unverschlüsselt (Fallback/Migration)
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw) {
    try {
      return JSON.parse(raw) as CompassProfile;
    } catch {
      // Korrupt — neues Profil
    }
  }

  return createEmptyProfile();
}

/** Speichert das Kompass-Profil. Verschlüsselt wenn Key vorhanden. */
export async function saveProfile(profile: CompassProfile, privateKeyHex: string | null): Promise<void> {
  if (typeof window === "undefined") return;

  const json = JSON.stringify(profile);

  if (privateKeyHex) {
    try {
      const key = await deriveAesKey(privateKeyHex);
      const encrypted = await encrypt(json, key);
      localStorage.setItem(STORAGE_KEY_ENCRYPTED, encrypted);
      localStorage.removeItem(STORAGE_KEY); // Unverschlüsselt entfernen
      return;
    } catch {
      // Fallback auf unverschlüsselt
    }
  }

  localStorage.setItem(STORAGE_KEY, json);
}

/** Löscht das Kompass-Profil vollständig */
export function clearProfile(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(STORAGE_KEY_ENCRYPTED);
}
