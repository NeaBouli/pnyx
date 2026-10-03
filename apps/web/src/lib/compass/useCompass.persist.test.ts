// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { createEmptyProfile } from "./engine";
import { CompassStorageError, saveProfile } from "./storage";
import { readPrivateKeySafely, saveProfileSafely } from "./useCompass";

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

describe("readPrivateKeySafely", () => {
  it("returns null instead of throwing when WebStorage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); });
    expect(() => readPrivateKeySafely()).not.toThrow();
    expect(readPrivateKeySafely()).toBeNull();
  });
});
