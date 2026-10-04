import { describe, expect, it } from "vitest";
import plugin from "./with-legacy-abi-excludes";

const { setLegacyAbiExcludes, LEGACY_ABI_EXCLUDES } = plugin as unknown as {
  setLegacyAbiExcludes: (properties: Array<Record<string, string>>) => Array<Record<string, string>>;
  LEGACY_ABI_EXCLUDES: string[];
};

describe("with-legacy-abi-excludes", () => {
  it("adds the legacy ABI excludes when the property is missing", () => {
    const result = setLegacyAbiExcludes([{ type: "property", key: "hermesEnabled", value: "true" }]);
    expect(result).toContainEqual({
      type: "property",
      key: "android.packagingOptions.excludes",
      value: "lib/armeabi/**,lib/mips/**,lib/mips64/**",
    });
  });

  it("keeps existing excludes and does not duplicate entries", () => {
    const properties = [
      { type: "property", key: "android.packagingOptions.excludes", value: "/LICENSE, lib/mips/**" },
    ];
    setLegacyAbiExcludes(properties);
    setLegacyAbiExcludes(properties);
    expect(properties[0].value).toBe("/LICENSE,lib/mips/**,lib/armeabi/**,lib/mips64/**");
  });

  it("never excludes an ABI that Android devices use", () => {
    for (const abi of ["arm64-v8a", "armeabi-v7a", "x86", "x86_64"]) {
      expect(LEGACY_ABI_EXCLUDES.some((pattern) => pattern === `lib/${abi}/**`)).toBe(false);
    }
  });
});
