import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { isZkSemaphoreFeatureEnabled } from "./zkSemaphoreCore";

// CODEX SECURITY-VOTUM ZK-ZKEY (2026-10-03): the ZK path stays off until the bundled,
// hash-pinned zkey (no network at vote time) passes the re-enable gate. Turning it back on
// must be a deliberate change to this test, not a silent app.json edit.
const appJson = JSON.parse(readFileSync(join(__dirname, "..", "..", "app.json"), "utf8")) as {
  expo: { extra?: Record<string, unknown> };
};

describe("ZK kill switch (mobile)", () => {
  it("ships with zkSemaphoreEnabled=false in app.json", () => {
    expect(appJson.expo.extra?.zkSemaphoreEnabled).toBe(false);
  });

  it("keeps the feature disabled when no build env override is set", () => {
    expect(isZkSemaphoreFeatureEnabled(appJson.expo.extra, undefined)).toBe(false);
  });
});
