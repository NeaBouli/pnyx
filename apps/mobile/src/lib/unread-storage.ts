/** Small SecureStore values; publish a new generation only after all chunks persist. */
import { UNREAD_EVENTS_STORAGE_KEY, UNREAD_FEED_SNAPSHOT_KEY } from "./unread-events";

interface Storage {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
}

const KEYS = new Set([UNREAD_EVENTS_STORAGE_KEY, UNREAD_FEED_SNAPSHOT_KEY]);
const CHUNK_BYTES = 1024;
const MAX_CHUNKS = 256;
interface Manifest { version: 1; bank: "a" | "b"; count: number; length: number }

function manifest(raw: string): Manifest {
  const value = JSON.parse(raw) as Manifest;
  if (!value || value.version !== 1 || !["a", "b"].includes(value.bank)
    || !Number.isInteger(value.count) || value.count < 1 || value.count > MAX_CHUNKS
    || !Number.isInteger(value.length) || value.length < 0 || value.length > CHUNK_BYTES * MAX_CHUNKS) {
    throw new Error("Invalid unread storage manifest");
  }
  return value;
}

function chunks(value: string): string[] {
  const result: string[] = [];
  let part = "";
  let bytes = 0;
  // Iterating code points keeps surrogate pairs intact without TextEncoder dependencies.
  for (const char of value) {
    const code = char.codePointAt(0)!;
    const size = code <= 0x7f ? 1 : code <= 0x7ff ? 2 : code <= 0xffff ? 3 : 4;
    if (bytes + size > CHUNK_BYTES) { result.push(part); part = ""; bytes = 0; }
    part += char;
    bytes += size;
    if (result.length >= MAX_CHUNKS) throw new Error("Unread storage bound exceeded");
  }
  result.push(part);
  return result;
}

export function createUnreadStorage(storage: Storage): Storage {
  let queue: Promise<unknown> = Promise.resolve();
  function serialized<T>(work: () => Promise<T>): Promise<T> {
    const pending = queue.then(work);
    queue = pending.catch(() => undefined);
    return pending;
  }
  return {
    getItem(key) {
      if (!KEYS.has(key)) return storage.getItem(key); // Existing preferences remain unchanged.
      return serialized(async () => {
        const raw = await storage.getItem(`${key}.manifest`);
        if (raw === null) return storage.getItem(key); // Read the unshipped legacy draft format.
        const current = manifest(raw);
        let value = "";
        for (let i = 0; i < current.count; i++) {
          const part = await storage.getItem(`${key}.${current.bank}.${i}`);
          if (part === null) throw new Error("Unread storage chunk missing");
          value += part;
          if (value.length > current.length) throw new Error("Unread storage length mismatch");
        }
        if (value.length !== current.length) throw new Error("Unread storage length mismatch");
        return value;
      });
    },
    setItem(key, value) {
      if (!KEYS.has(key)) return Promise.reject(new Error("Unmanaged unread storage key"));
      return serialized(async () => {
        const parts = chunks(value);
        const raw = await storage.getItem(`${key}.manifest`);
        const bank = raw === null || manifest(raw).bank === "b" ? "a" : "b";
        for (let i = 0; i < parts.length; i++) await storage.setItem(`${key}.${bank}.${i}`, parts[i]);
        // Never overwrite the currently committed bank. Interrupted writes retain the old value.
        await storage.setItem(`${key}.manifest`, JSON.stringify({ version: 1, bank, count: parts.length, length: value.length }));
      });
    },
  };
}
