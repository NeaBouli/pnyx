import { describe, expect, it } from "vitest";
import { getNativeSemaphoreStatus } from "./zkSemaphoreNativeCore";

describe("getNativeSemaphoreStatus", () => {
  it("reports missing modules when the native prover is not bundled", () => {
    const result = getNativeSemaphoreStatus(() => {
      throw new Error("module not found");
    });

    expect(result.ready).toBe(false);
    expect(result.present).toEqual([]);
    expect(result.missing).toEqual(["Identity", "Group", "Proof"]);
  });

  it("requires all Semaphore native modules before reporting ready", () => {
    const result = getNativeSemaphoreStatus((name) => {
      if (name === "Proof") throw new Error("missing proof module");
      return {};
    });

    expect(result.ready).toBe(false);
    expect(result.present).toEqual(["Identity", "Group"]);
    expect(result.missing).toEqual(["Proof"]);
  });

  it("reports ready when Identity, Group, and Proof modules are bundled", () => {
    const result = getNativeSemaphoreStatus(() => ({}));

    expect(result.ready).toBe(true);
    expect(result.present).toEqual(["Identity", "Group", "Proof"]);
    expect(result.missing).toEqual([]);
  });
});
