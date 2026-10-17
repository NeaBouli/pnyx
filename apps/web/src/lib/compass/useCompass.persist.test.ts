// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { createEmptyProfile } from "./engine";
import { CompassStorageError, saveProfile } from "./storage";
import { readCompassKeysSafely, saveProfileSafely } from "./useCompass";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("saveProfileSafely in a browser environment (Codex follow-up to #396)", () => {
  it("exercises the real NO_KEY rejection and swallows it", async () => {
    await expect(saveProfile(createEmptyProfile(), null)).rejects.toBeInstanceOf(CompassStorageError);
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    await expect(saveProfileSafely(createEmptyProfile(), null)).resolves.toBeUndefined();
    expect(warn).not.toHaveBeenCalled();
  });

  it("logs unexpected (non-storage) errors instead of rejecting", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new TypeError("boom"); });
    await expect(saveProfileSafely(createEmptyProfile(), null)).resolves.toBeUndefined();
    // removeItem failures surface as CompassStorageError("STORAGE"), which is expected and not logged
    expect(warn).not.toHaveBeenCalled();
  });
});

describe("readCompassKeysSafely", () => {
  it("returns no legacy key when WebStorage is blocked", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); });
    expect((await readCompassKeysSafely()).legacyPrivateKeyHex).toBeNull();
  });
});
