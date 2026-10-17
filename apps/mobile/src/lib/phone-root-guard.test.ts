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

import { registerTier1, storeNullifierRoot } from "./crypto-native";

const REPO = join(__dirname, "../../../..");
const ROOTS = [
  "apps/mobile/src",
  "apps/mobile/App.tsx",
  "apps/mobile/index.ts",
  "apps/mobile/app.config.js",
  "apps/web/src",
  "apps/representative",
];
// Apps must not import the TS crypto package at all (none does today); its
// root functions are also no longer exported from its public index.
const PACKAGE_IMPORT = /from\s+["'](@ekklesia\/crypto|[./]*packages\/crypto)[^"']*["']|import\(\s*["'](@ekklesia\/crypto|[./]*packages\/crypto)/;
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

  it("no application source imports the TS crypto package", () => {
    const offenders = ROOTS.flatMap(sources)
      .filter((f) => /\.(ts|tsx|js|jsx)$/.test(f) && !/\.test\.(ts|tsx)$/.test(f))
      .map((f) => relative(REPO, f))
      .filter((rel) => PACKAGE_IMPORT.test(readFileSync(join(REPO, rel), "utf8")));
    expect(offenders).toEqual([]);
  });

  it("the package index does not export the root functions", () => {
    const index = readFileSync(join(REPO, "packages/crypto/src/index.ts"), "utf8");
    const exported = index.replace(/\/\/[^\n]*/g, "");
    expect(exported).not.toMatch(/\b(deriveNullifierRoot|persistNullifierRoot|buildRegistrationPayload)\b/);
  });

  it("registerTier1 and storeNullifierRoot always throw (runtime enforcement)", async () => {
    await expect(registerTier1("+306912345678")).rejects.toThrow("ADR-006 D1");
    await expect(storeNullifierRoot(new Uint8Array(32))).rejects.toThrow("ADR-006 D1");
  });
});
