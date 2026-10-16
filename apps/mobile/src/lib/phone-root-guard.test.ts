/**
 * ADR-006 D1 guard: phone-derived client roots (public salt) must never be
 * created by application code. Only crypto-native.ts / the package define the
 * functions (for KAT vectors); no other source file may call them.
 */
import { describe, expect, it, vi } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn(async () => null),
  setItemAsync: vi.fn(async () => {}),
  deleteItemAsync: vi.fn(async () => {}),
}));

import { registerTier1 } from "./crypto-native";

const REPO = join(__dirname, "../../../..");
const ROOTS = ["apps/mobile/src", "apps/mobile/App.tsx", "apps/web/src", "apps/representative"];
const FORBIDDEN = /\b(registerTier1|deriveNullifierRoot|storeNullifierRoot|persistNullifierRoot|buildRegistrationPayload)\b/;
const ALLOWED = new Set(["apps/mobile/src/lib/crypto-native.ts"]);

function sources(path: string): string[] {
  const abs = join(REPO, path);
  let st;
  try {
    st = statSync(abs);
  } catch {
    return [];
  }
  if (st.isFile()) return [abs];
  return readdirSync(abs).flatMap((name) => {
    if (name === "node_modules" || name.startsWith(".")) return [];
    return sources(join(path, name));
  });
}

describe("ADR-006 D1: no phone-derived client roots", () => {
  it("no application source calls the forbidden root functions", () => {
    const offenders = ROOTS.flatMap(sources)
      .filter((f) => /\.(ts|tsx|js|jsx)$/.test(f) && !/\.test\.(ts|tsx)$/.test(f))
      .map((f) => relative(REPO, f))
      .filter((rel) => !ALLOWED.has(rel))
      .filter((rel) => FORBIDDEN.test(readFileSync(join(REPO, rel), "utf8")));
    expect(offenders).toEqual([]);
  });

  it("registerTier1 always throws", async () => {
    await expect(registerTier1("+306912345678")).rejects.toThrow("ADR-006 D1");
  });
});
