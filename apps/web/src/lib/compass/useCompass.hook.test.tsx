// @vitest-environment jsdom
import { act, createElement, useEffect } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const saveSpy = vi.hoisted(() => ({ impl: null as null | ((...a: unknown[]) => Promise<void>), calls: 0 }));

vi.mock("./storage", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./storage")>();
  return {
    ...actual,
    saveProfile: (...args: Parameters<typeof actual.saveProfile>) => {
      saveSpy.calls += 1;
      return saveSpy.impl ? saveSpy.impl(...args) : actual.saveProfile(...args);
    },
  };
});

import { CompassStorageError, saveProfile } from "./storage";
import { saveProfileSafely, useCompass } from "./useCompass";
import { createEmptyProfile } from "./engine";

type Api = ReturnType<typeof useCompass>;

function Harness({ onApi }: { onApi: (api: Api) => void }) {
  const api = useCompass();
  useEffect(() => { onApi(api); });
  return null;
}

let root: Root;
let container: HTMLDivElement;
let api: Api;

beforeEach(async () => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  localStorage.clear();
  saveSpy.impl = null;
  saveSpy.calls = 0;
  vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 404 })));
  container = document.createElement("div");
  root = createRoot(container);
  await act(async () => { root.render(createElement(Harness, { onApi: (a: Api) => { api = a; } })); });
  await act(async () => { await Promise.resolve(); });
});

afterEach(() => {
  act(() => root.unmount());
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("useCompass debounced persistence (Codex follow-up to #441)", () => {
  it("saveProfile rejects with code NO_KEY when no key is stored", async () => {
    await expect(saveProfile(createEmptyProfile(), null)).rejects.toMatchObject({ code: "NO_KEY" });
    await expect(saveProfile(createEmptyProfile(), null)).rejects.toBeInstanceOf(CompassStorageError);
  });

  it("debounces rapid changes into one keyless save without an unhandled rejection or warning", async () => {
    expect(api.loading).toBe(false);
    vi.useFakeTimers();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    await act(async () => {
      api.setModel("left-right");
      api.setModel("compass-2d");
      api.setModel("thematic-radar");
    });
    expect(saveSpy.calls).toBe(0);
    await act(async () => { await vi.advanceTimersByTimeAsync(299); });
    expect(saveSpy.calls).toBe(0);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(saveSpy.calls).toBe(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(saveSpy.calls).toBe(1);
    expect(warn).not.toHaveBeenCalled();
    expect(localStorage.getItem("ekklesia_compass_profile")).toBeNull();
    expect(localStorage.getItem("ekklesia_compass_encrypted")).toBeNull();
  });

  it("logs unexpected (non-CompassStorageError) save failures instead of rejecting", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    saveSpy.impl = async () => { throw new TypeError("unexpected"); };
    await expect(saveProfileSafely(createEmptyProfile(), "00")).resolves.toBeUndefined();
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0][1]).toBeInstanceOf(TypeError);
  });
});
