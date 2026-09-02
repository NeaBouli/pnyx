import { describe, expect, it, vi } from "vitest";

vi.mock("expo-application", () => ({
  nativeApplicationVersion: "1.0.31",
  nativeBuildVersion: "60",
}));
vi.mock("expo-constants", () => ({ default: { expoConfig: undefined } }));

import {
  getCurrentVersionCode,
  getCurrentVersionName,
  parseNativeVersionCode,
} from "./app-version";

describe("native app version", () => {
  it("uses the Android package version code", () => {
    expect(parseNativeVersionCode("60", 5)).toBe(60);
    expect(parseNativeVersionCode("584", 59)).toBe(584);
  });

  it("falls back when no valid native build version is available", () => {
    expect(parseNativeVersionCode(null, 59)).toBe(59);
    expect(parseNativeVersionCode("invalid", 59)).toBe(59);
    expect(parseNativeVersionCode("59x", 58)).toBe(58);
    expect(parseNativeVersionCode("59.9", 58)).toBe(58);
    expect(parseNativeVersionCode(" 59", 58)).toBe(58);
  });

  it("reads the installed package version instead of embedded Expo metadata", () => {
    expect(getCurrentVersionName()).toBe("1.0.31");
    expect(getCurrentVersionCode()).toBe(60);
  });
});
