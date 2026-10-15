import { beforeEach, describe, expect, it, vi } from "vitest";

const store = vi.hoisted(() => new Map<string, string>());

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn(async (key: string) => store.get(key) ?? null),
  setItemAsync: vi.fn(async (key: string, value: string) => { store.set(key, value); }),
  deleteItemAsync: vi.fn(async (key: string) => { store.delete(key); }),
}));
vi.mock("expo-constants", () => ({ default: { expoConfig: { extra: { distributionChannel: "play" } } } }));

import { activateDemo, clearDemo, DEMO_NULLIFIER_PREFIX, isDemoMode } from "./demo";

describe("demo mode (audit F4)", () => {
  beforeEach(() => store.clear());

  it("is active for the synthetic demo identity", async () => {
    store.set("ekklesia_nullifier", `${DEMO_NULLIFIER_PREFIX}18f00`);
    await activateDemo();
    expect(await isDemoMode()).toBe(true);
  });

  it("a stale demo flag next to a real identity is NOT demo mode (no simulated vote)", async () => {
    await activateDemo();
    store.set("ekklesia_nullifier", "a".repeat(64));
    expect(await isDemoMode()).toBe(false);
  });

  it("without any identity the flag alone is not demo mode", async () => {
    await activateDemo();
    expect(await isDemoMode()).toBe(false);
  });

  it("clearDemo ends demo mode", async () => {
    store.set("ekklesia_nullifier", `${DEMO_NULLIFIER_PREFIX}1`);
    await activateDemo();
    await clearDemo();
    expect(await isDemoMode()).toBe(false);
  });
});
