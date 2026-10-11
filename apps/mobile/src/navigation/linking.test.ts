import { describe, expect, it } from "vitest";
import { getStateFromPath } from "@react-navigation/core";

import { linking } from "./linking";

const KEY = "01".repeat(32);

describe("deep links (EVA-034)", () => {
  it("does not map import-account to any screen", () => {
    expect(JSON.stringify(linking.config.screens)).not.toContain("import-account");
    expect(Object.keys(linking.config.screens)).not.toContain("ImportAccount");
  });

  it("an external import-account link does not reach the import screen", () => {
    const state = getStateFromPath(`import-account?key=${KEY}&nullifier=${KEY}&pubkey=${KEY}`, linking.config);
    expect(JSON.stringify(state ?? {})).not.toContain("ImportAccount");
  });

  it("keeps the existing POLIS login and bill links", () => {
    expect(JSON.stringify(getStateFromPath("polis-login", linking.config))).toContain("PolisLogin");
    expect(JSON.stringify(getStateFromPath("el/bills/GR-1", linking.config))).toContain("GR-1");
  });
});
