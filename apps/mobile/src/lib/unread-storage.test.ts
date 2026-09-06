import { describe, expect, it, vi } from "vitest";
import { createUnreadStorage } from "./unread-storage";
import {
  UNREAD_EVENTS_STORAGE_KEY,
  UNREAD_FEED_SNAPSHOT_KEY,
} from "./unread-events";

const KEY = UNREAD_EVENTS_STORAGE_KEY;
const SNAP = UNREAD_FEED_SNAPSHOT_KEY;

/** The documented native SecureStore value limit; the mock enforces it strictly. */
const NATIVE_LIMIT_BYTES = 2048;
const CHUNK_BYTES = 1024;
const MAX_CHUNKS = 256;
const MAX_VALUE_BYTES = CHUNK_BYTES * MAX_CHUNKS;

function utf8Bytes(value: string): number {
  return new TextEncoder().encode(value).length;
}

interface WriteRecord {
  key: string;
  value: string;
  bytes: number;
}

/**
 * In-memory stand-in for the native SecureStore. Unlike the installed JS
 * wrapper (which only warns above 2048 bytes), this mock REJECTS every write
 * above the documented 2048-byte native limit, so the adapter's chunking
 * contract is verified against the strictest interpretation of the platform.
 */
function strictSecureStore(initial: Record<string, string> = {}) {
  const map = new Map<string, string>(Object.entries(initial));
  const writes: WriteRecord[] = [];
  const failures = new Map<string, number>();
  return {
    map,
    writes,
    /** Make the next `times` native writes to `key` reject (crash simulation). */
    failNextWrites(key: string, times = 1) {
      failures.set(key, times);
    },
    getItem: vi.fn(async (key: string) => map.get(key) ?? null),
    setItem: vi.fn(async (key: string, value: string) => {
      const bytes = utf8Bytes(value);
      if (bytes > NATIVE_LIMIT_BYTES) {
        throw new Error(
          `native SecureStore rejected ${bytes}-byte value for ${key}`,
        );
      }
      const pending = failures.get(key) ?? 0;
      if (pending > 0) {
        failures.set(key, pending - 1);
        throw new Error(`injected native write failure for ${key}`);
      }
      writes.push({ key, value, bytes });
      map.set(key, value);
    }),
  };
}

/** A full 50-event ledger with Greek titles and emoji, plus 100 tombstones. */
function ledgerValue(events = 50, tombstones = 100): string {
  const list = [];
  for (let i = 0; i < events; i += 1) {
    list.push({
      id: `vote_open:DIAV-Ρ9Ζ546ΜΤΛΒ-${i}`,
      templateId: "vote_open",
      title:
        "🗳️ Νέα Ψηφοφορία · Νομοσχέδιο για την ενίσχυση της τοπικής αυτοδιοίκησης και τη διαφάνεια",
      body: "Η ψηφοφορία ξεκίνησε · Συμμετάσχετε τώρα 🗳️ ⏰",
      billId: `DIAV-Ρ9Ζ546ΜΤΛΒ-${i}`,
    });
  }
  const read = [];
  for (let i = 0; i < tombstones; i += 1) {
    read.push(`vote_result:DIAV-ΠΛΗΡΕΣ-ΑΡΧΕΙΟ-${i}`);
  }
  return JSON.stringify({ events: list, read });
}

/** A full 500-entry feed snapshot with Greek DIAV bill IDs. */
function snapshotValue(entries = 500): string {
  const rows: [string, string][] = [];
  for (let i = 0; i < entries; i += 1) {
    rows.push([`DIAV-Ρ9Ζ546ΜΤΛΒ-${i}`, i % 2 === 0 ? "ACTIVE" : "ANNOUNCED"]);
  }
  return JSON.stringify(rows);
}

function manifestOf(storage: ReturnType<typeof strictSecureStore>, key: string) {
  const raw = storage.map.get(`${key}.manifest`);
  return raw === undefined ? null : JSON.parse(raw);
}

describe("chunked roundtrips under a strict 2048-byte native store", () => {
  it("roundtrips a 50-event Greek/emoji ledger across multiple chunks", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    const value = ledgerValue(50, 100);
    // The payload far exceeds a single native value; chunking is mandatory.
    expect(utf8Bytes(value)).toBeGreaterThan(NATIVE_LIMIT_BYTES);

    await adapter.setItem(KEY, value);
    expect(await adapter.getItem(KEY)).toBe(value);

    const manifest = manifestOf(storage, KEY);
    expect(manifest).toMatchObject({ version: 1, bank: "a" });
    expect(manifest.count).toBeGreaterThan(1);
    expect(manifest.count).toBeLessThanOrEqual(MAX_CHUNKS);
    expect(manifest.length).toBe(value.length);
    // Every native write — chunks and manifest — stayed inside the limit.
    for (const write of storage.writes) {
      expect(write.bytes).toBeLessThanOrEqual(NATIVE_LIMIT_BYTES);
    }
    const chunkWrites = storage.writes.filter((w) =>
      w.key.startsWith(`${KEY}.a.`),
    );
    expect(chunkWrites.length).toBe(manifest.count);
    for (const write of chunkWrites) {
      expect(write.bytes).toBeLessThanOrEqual(CHUNK_BYTES);
    }
  });

  it("roundtrips a 500-entry Greek snapshot across multiple chunks", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    const value = snapshotValue(500);
    expect(utf8Bytes(value)).toBeGreaterThan(NATIVE_LIMIT_BYTES);

    await adapter.setItem(SNAP, value);
    expect(await adapter.getItem(SNAP)).toBe(value);
    expect(manifestOf(storage, SNAP)?.count).toBeGreaterThan(1);
    for (const write of storage.writes) {
      expect(write.bytes).toBeLessThanOrEqual(NATIVE_LIMIT_BYTES);
    }
  });

  it("keeps the ledger and snapshot keys fully independent", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    const ledger = ledgerValue(50, 100);
    const snapshot = snapshotValue(500);

    await adapter.setItem(KEY, ledger);
    await adapter.setItem(SNAP, snapshot);

    expect(await adapter.getItem(KEY)).toBe(ledger);
    expect(await adapter.getItem(SNAP)).toBe(snapshot);
    for (const key of storage.map.keys()) {
      if (key.startsWith(`${KEY}.`)) expect(key).not.toContain(SNAP);
      if (key.startsWith(`${SNAP}.`)) expect(key).not.toContain(KEY);
    }
  });

  it("roundtrips across an adapter restart over the same native store", async () => {
    const storage = strictSecureStore();
    const value = ledgerValue(50, 100);
    await createUnreadStorage(storage).setItem(KEY, value);

    // A fresh adapter has an empty serialization queue and no cached state.
    const restarted = createUnreadStorage(storage);
    expect(await restarted.getItem(KEY)).toBe(value);
  });

  it("roundtrips an empty string as a single empty chunk", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    await adapter.setItem(KEY, "");
    expect(await adapter.getItem(KEY)).toBe("");
    expect(manifestOf(storage, KEY)).toMatchObject({
      bank: "a",
      count: 1,
      length: 0,
    });
  });
});

describe("chunk boundaries and multibyte safety", () => {
  it("splits Greek text on the 1024-byte boundary without breaking characters", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    // 513 × 'Ω' (2 UTF-8 bytes) = 1026 bytes → chunks of 512 and 1 chars.
    const value = "Ω".repeat(513);
    await adapter.setItem(KEY, value);

    expect(await adapter.getItem(KEY)).toBe(value);
    expect(storage.map.get(`${KEY}.a.0`)).toBe("Ω".repeat(512));
    expect(storage.map.get(`${KEY}.a.1`)).toBe("Ω");
  });

  it("never splits a surrogate pair across chunks", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    // 1023 ASCII bytes followed by a 4-byte emoji: the emoji cannot fit in
    // the first chunk and must move to the second as an intact code point.
    const value = `${"a".repeat(CHUNK_BYTES - 1)}😀`;
    await adapter.setItem(KEY, value);

    const first = storage.map.get(`${KEY}.a.0`)!;
    const second = storage.map.get(`${KEY}.a.1`)!;
    expect(first).toBe("a".repeat(CHUNK_BYTES - 1));
    expect(second).toBe("😀");
    // The pair travelled together: no lone surrogate in either chunk.
    expect(second.length).toBe(2);
    expect(second.charCodeAt(0)).toBe(0xd83d);
    expect(second.charCodeAt(1)).toBe(0xde00);
    expect(await adapter.getItem(KEY)).toBe(value);
  });

  it("accepts a value at the exact 256-chunk bound", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    const value = "a".repeat(MAX_VALUE_BYTES);
    await adapter.setItem(KEY, value);

    expect(await adapter.getItem(KEY)).toBe(value);
    expect(manifestOf(storage, KEY)?.count).toBe(MAX_CHUNKS);
    for (const write of storage.writes) {
      expect(write.bytes).toBeLessThanOrEqual(NATIVE_LIMIT_BYTES);
    }
  });
});

describe("bounds are enforced before any native write", () => {
  it("rejects an over-bound value without touching the native store", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    const oversized = "a".repeat(MAX_VALUE_BYTES + 1);

    await expect(adapter.setItem(KEY, oversized)).rejects.toThrow(
      /bound exceeded/i,
    );
    // No partial chunks, no manifest, not even a manifest read: the bound
    // is evaluated before any native interaction.
    expect(storage.setItem).not.toHaveBeenCalled();
    expect(storage.getItem).not.toHaveBeenCalled();
    expect(storage.map.size).toBe(0);
  });

  it("rejects a multibyte value whose UTF-8 size exceeds the bound", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    // 131073 × 'Ω' = 262146 UTF-8 bytes > 256 × 1024, while the JS string
    // length alone would look smaller than the byte bound.
    const oversized = "Ω".repeat(MAX_VALUE_BYTES / 2 + 1);

    await expect(adapter.setItem(KEY, oversized)).rejects.toThrow(
      /bound exceeded/i,
    );
    expect(storage.setItem).not.toHaveBeenCalled();
    expect(storage.map.size).toBe(0);
  });
});

describe("manifest publication and bank alternation", () => {
  it("publishes the manifest only after every chunk of the new bank persisted", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    await adapter.setItem(KEY, ledgerValue(50, 100));

    const manifestIndex = storage.writes.findIndex(
      (w) => w.key === `${KEY}.manifest`,
    );
    const chunkIndexes = storage.writes
      .map((w, i) => (w.key.startsWith(`${KEY}.a.`) ? i : -1))
      .filter((i) => i >= 0);
    expect(chunkIndexes.length).toBeGreaterThan(1);
    expect(manifestIndex).toBeGreaterThan(Math.max(...chunkIndexes));
  });

  it("alternates banks and never overwrites the currently committed bank", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);

    await adapter.setItem(KEY, ledgerValue(50, 100));
    expect(manifestOf(storage, KEY)?.bank).toBe("a");
    const firstGeneration = storage.writes.length;

    await adapter.setItem(KEY, snapshotValue(500));
    expect(manifestOf(storage, KEY)?.bank).toBe("b");
    const secondGeneration = storage.writes.slice(firstGeneration);
    // Every chunk write of the second generation targeted bank b; the
    // committed bank a chunks were left untouched until the manifest flipped.
    const chunks = secondGeneration.filter((w) => w.key !== `${KEY}.manifest`);
    expect(chunks.length).toBeGreaterThan(1);
    for (const write of chunks) {
      expect(write.key.startsWith(`${KEY}.b.`)).toBe(true);
    }

    await adapter.setItem(KEY, ledgerValue(50, 100));
    expect(manifestOf(storage, KEY)?.bank).toBe("a");
  });
});

describe("interrupted writes preserve the old committed value", () => {
  it("survives a crash mid-chunk and recovers on retry", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    const oldValue = ledgerValue(50, 100);
    const newValue = snapshotValue(500);
    await adapter.setItem(KEY, oldValue);

    // The new generation needs many chunks; the third one never persists.
    storage.failNextWrites(`${KEY}.b.2`);
    await expect(adapter.setItem(KEY, newValue)).rejects.toThrow(/injected/);

    // The manifest still commits bank a: reads return the old value intact.
    expect(manifestOf(storage, KEY)?.bank).toBe("a");
    expect(await adapter.getItem(KEY)).toBe(oldValue);

    // The failed operation did not poison the serialized queue: a plain
    // retry rewrites the new bank and publishes it.
    await adapter.setItem(KEY, newValue);
    expect(await adapter.getItem(KEY)).toBe(newValue);
    expect(manifestOf(storage, KEY)?.bank).toBe("b");
  });

  it("survives a crash on the manifest write itself and recovers on retry", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    const oldValue = ledgerValue(50, 100);
    const newValue = snapshotValue(500);
    await adapter.setItem(KEY, oldValue);

    storage.failNextWrites(`${KEY}.manifest`);
    await expect(adapter.setItem(KEY, newValue)).rejects.toThrow(/injected/);

    // All new chunks persisted, but without the manifest flip the old
    // value remains the only committed one.
    expect(manifestOf(storage, KEY)?.bank).toBe("a");
    expect(await adapter.getItem(KEY)).toBe(oldValue);

    await adapter.setItem(KEY, newValue);
    expect(await adapter.getItem(KEY)).toBe(newValue);
    expect(manifestOf(storage, KEY)?.bank).toBe("b");
  });

  it("keeps serving reads after a failed write (queue is not poisoned)", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    const value = ledgerValue(50, 100);
    await adapter.setItem(KEY, value);

    storage.failNextWrites(`${KEY}.manifest`);
    await expect(adapter.setItem(KEY, "x".repeat(3000))).rejects.toThrow();
    // Several queued operations after the failure all proceed normally.
    await expect(adapter.getItem(KEY)).resolves.toBe(value);
    await expect(adapter.getItem(SNAP)).resolves.toBeNull();
    await adapter.setItem(SNAP, snapshotValue(500));
    await expect(adapter.getItem(SNAP)).resolves.toBe(snapshotValue(500));
  });
});

describe("legacy draft-format reads", () => {
  it("reads the unshipped legacy draft value when no manifest exists", async () => {
    const legacy = ledgerValue(50, 100);
    const storage = strictSecureStore({ [KEY]: legacy });
    const adapter = createUnreadStorage(storage);

    expect(await adapter.getItem(KEY)).toBe(legacy);
    expect(storage.getItem).toHaveBeenCalledWith(`${KEY}.manifest`);
    expect(storage.getItem).toHaveBeenCalledWith(KEY);
  });

  it("returns null for a managed key that was never written", async () => {
    const adapter = createUnreadStorage(strictSecureStore());
    expect(await adapter.getItem(KEY)).toBeNull();
    expect(await adapter.getItem(SNAP)).toBeNull();
  });

  it("prefers the chunked generation once a manifest exists", async () => {
    const legacy = "legacy-draft-value";
    const storage = strictSecureStore({ [KEY]: legacy });
    const adapter = createUnreadStorage(storage);
    const value = ledgerValue(50, 100);

    await adapter.setItem(KEY, value);
    expect(await adapter.getItem(KEY)).toBe(value);
  });
});

describe("corrupt or incomplete persisted state fails closed", () => {
  const corruptManifests: Array<[string, string]> = [
    ["not JSON", "{not-json"],
    ["wrong version", JSON.stringify({ version: 2, bank: "a", count: 1, length: 1 })],
    ["unknown bank", JSON.stringify({ version: 1, bank: "c", count: 1, length: 1 })],
    ["zero count", JSON.stringify({ version: 1, bank: "a", count: 0, length: 0 })],
    ["count above max", JSON.stringify({ version: 1, bank: "a", count: 257, length: 1 })],
    ["fractional count", JSON.stringify({ version: 1, bank: "a", count: 1.5, length: 1 })],
    ["negative length", JSON.stringify({ version: 1, bank: "a", count: 1, length: -1 })],
    ["length above max", JSON.stringify({ version: 1, bank: "a", count: 1, length: MAX_VALUE_BYTES + 1 })],
    ["missing fields", JSON.stringify({ version: 1 })],
    ["array instead of object", JSON.stringify([1, "a", 1, 1])],
  ];

  it.each(corruptManifests)(
    "rejects a corrupt manifest (%s) instead of falling back to the legacy draft",
    async (_name, raw) => {
      const storage = strictSecureStore({
        [KEY]: "legacy-draft-value",
        [`${KEY}.manifest`]: raw,
      });
      const adapter = createUnreadStorage(storage);

      await expect(adapter.getItem(KEY)).rejects.toThrow();
      // Fail closed: the legacy draft is NOT served when a manifest exists.
      expect(storage.getItem).not.toHaveBeenCalledWith(KEY);
    },
  );

  it("rejects when a chunk referenced by a valid manifest is missing", async () => {
    const value = ledgerValue(50, 100);
    const storage = strictSecureStore();
    await createUnreadStorage(storage).setItem(KEY, value);
    const manifest = manifestOf(storage, KEY)!;
    expect(manifest.count).toBeGreaterThan(2);
    storage.map.delete(`${KEY}.a.1`);

    await expect(createUnreadStorage(storage).getItem(KEY)).rejects.toThrow(
      /missing/i,
    );
  });

  it("rejects when concatenated chunks are longer than the manifest length", async () => {
    const value = ledgerValue(50, 100);
    const storage = strictSecureStore();
    await createUnreadStorage(storage).setItem(KEY, value);
    const manifest = manifestOf(storage, KEY)!;
    storage.map.set(
      `${KEY}.manifest`,
      JSON.stringify({ ...manifest, length: manifest.length - 1 }),
    );

    await expect(createUnreadStorage(storage).getItem(KEY)).rejects.toThrow(
      /length mismatch/i,
    );
  });

  it("rejects when concatenated chunks are shorter than the manifest length", async () => {
    const value = ledgerValue(50, 100);
    const storage = strictSecureStore();
    await createUnreadStorage(storage).setItem(KEY, value);
    const manifest = manifestOf(storage, KEY)!;
    storage.map.set(
      `${KEY}.manifest`,
      JSON.stringify({ ...manifest, length: manifest.length + 1 }),
    );

    await expect(createUnreadStorage(storage).getItem(KEY)).rejects.toThrow(
      /length mismatch/i,
    );
  });
});

describe("serialization of concurrent operations", () => {
  it("never exposes a torn read while a chunked write is in flight", async () => {
    const storage = strictSecureStore();
    const adapter = createUnreadStorage(storage);
    const oldValue = ledgerValue(50, 100);
    const newValue = snapshotValue(500);
    await adapter.setItem(KEY, oldValue);

    const [first, second, third] = await Promise.all([
      adapter.setItem(KEY, newValue).then(() => adapter.getItem(KEY)),
      adapter.getItem(KEY),
      adapter.getItem(KEY),
    ]);
    // Every read observed a complete generation — old or new, never a
    // mixture and never a missing-chunk rejection.
    for (const observed of [first, second, third]) {
      expect(observed).toBe(newValue);
    }
    expect(await adapter.getItem(KEY)).toBe(newValue);
  });
});

describe("key ownership boundaries", () => {
  it("passes unrelated preference reads straight through to the native store", async () => {
    const storage = strictSecureStore({ theme: "dark", locale: "el" });
    const adapter = createUnreadStorage(storage);

    expect(await adapter.getItem("theme")).toBe("dark");
    expect(await adapter.getItem("locale")).toBe("el");
    expect(await adapter.getItem("missing-pref")).toBeNull();
    // No manifest or chunk machinery is involved for unmanaged keys.
    expect(storage.getItem).not.toHaveBeenCalledWith("theme.manifest");
    expect(storage.getItem).toHaveBeenCalledTimes(3);
  });

  it("rejects writes to any key outside the unread ledger and snapshot", async () => {
    const storage = strictSecureStore({ theme: "dark" });
    const adapter = createUnreadStorage(storage);

    await expect(adapter.setItem("theme", "light")).rejects.toThrow(
      /unmanaged/i,
    );
    await expect(
      adapter.setItem(`${KEY}.manifest`, "{}"),
    ).rejects.toThrow(/unmanaged/i);
    await expect(adapter.setItem(`${KEY}_old`, "x")).rejects.toThrow(
      /unmanaged/i,
    );
    // Nothing reached the native store and the preference is untouched.
    expect(storage.setItem).not.toHaveBeenCalled();
    expect(storage.map.get("theme")).toBe("dark");
  });
});
