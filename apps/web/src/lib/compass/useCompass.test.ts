import { describe, expect, it } from "vitest";
import { computeResult, createEmptyProfile, seedFromVAA } from "./engine";
import { deriveCompassResult } from "./useCompass";

describe("derived compass result", () => {
  it("keeps an empty or unselected profile without a result", () => {
    const empty = createEmptyProfile();
    expect(deriveCompassResult(empty, null)).toBeNull();
    expect(deriveCompassResult({ ...empty, selectedModel: "left-right" }, null)).toBeNull();
    const unselected = seedFromVAA(empty, { 1: 1 }, { 1: "Υγεία" });
    expect(deriveCompassResult(unselected, null)).toBeNull();
  });

  it.each(["left-right", "compass-2d", "thematic-radar"] as const)(
    "preserves %s results without changing the stored profile", (model) => {
      const profile = {
        ...seedFromVAA(createEmptyProfile(), { 1: 1, 2: -1 }, { 1: "Υγεία", 2: "Παιδεία" }),
        selectedModel: model,
      };
      const before = structuredClone(profile);
      expect(deriveCompassResult(profile, null)).toEqual(computeResult(profile, model));
      expect(profile).toEqual(before);
      expect(deriveCompassResult(createEmptyProfile(), null)).toBeNull();
    },
  );

  it("waits for party data and preserves numeric statement conversion", () => {
    const profile = {
      ...seedFromVAA(createEmptyProfile(), { 1: 1 }, { 1: "Υγεία" }),
      selectedModel: "party-match" as const,
    };
    expect(deriveCompassResult(profile, null)).toBeNull();
    const data = { parties: { TEST: { id: 1, nameEl: "Test", colorHex: "#000000", positions: { "1": 1 } } }, statementCategories: {} };
    const before = structuredClone(data);
    expect(deriveCompassResult(profile, data)).toEqual(computeResult(profile, "party-match",
      { TEST: { 1: 1 } }, { TEST: { id: 1, nameEl: "Test", colorHex: "#000000" } }));
    expect(data).toEqual(before);
  });
});
