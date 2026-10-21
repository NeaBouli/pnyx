import { describe, expect, it } from "vitest";
import { getTabBarMetrics, TAB_BAR_MAX_FONT_SIZE_MULTIPLIER } from "./tab-bar-layout";

describe("bottom tab sizing (GH-298)", () => {
  it.each([
    { fontScale: 1, height: 56, iconWidth: 31, iconHeight: 28 },
    { fontScale: 1.3, height: 73, iconWidth: 41, iconHeight: 37 },
    { fontScale: 1.8, height: 79, iconWidth: 44, iconHeight: 40 },
  ])("reserves space for scale $fontScale, with and without a bottom inset", expected => {
    for (const bottomInset of [0, 24]) {
      const metrics = getTabBarMetrics(expected.fontScale, bottomInset);
      expect(metrics).toEqual({
        height: expected.height + bottomInset,
        iconWidth: expected.iconWidth,
        iconHeight: expected.iconHeight,
      });
      // Include the scaled label line, button padding and top border.
      const labelHeight = 14 * Math.min(expected.fontScale, TAB_BAR_MAX_FONT_SIZE_MULTIPLIER);
      expect(metrics.height - bottomInset).toBeGreaterThanOrEqual(metrics.iconHeight + labelHeight + 11);
      expect(metrics.height - bottomInset).toBeGreaterThanOrEqual(48);
    }
  });

  it("keeps the minimum touch height at smaller scales and caps growth with the text", () => {
    expect(getTabBarMetrics(0.8, 0)).toEqual(getTabBarMetrics(1, 0));
    expect(getTabBarMetrics(1.8, 24)).toEqual(getTabBarMetrics(TAB_BAR_MAX_FONT_SIZE_MULTIPLIER, 24));
    expect(getTabBarMetrics(3, 24)).toEqual(getTabBarMetrics(1.8, 24));
  });
});
