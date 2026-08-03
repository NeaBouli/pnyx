import { describe, expect, it } from "vitest";
import { availableGeographicFilters, scopedBillQuery } from "./bill-scope";

describe("scopedBillQuery", () => {
  it("fails closed to national bills without a verified location", () => {
    expect(scopedBillQuery({ periferiaId: null, dimosId: null })).toEqual({
      governance: "NATIONAL",
      include_institutional: false,
    });
  });

  it("includes national and the matching region through the API scope", () => {
    expect(scopedBillQuery({ periferiaId: 6, dimosId: null })).toEqual({
      periferia_id: 6,
      include_institutional: false,
    });
  });

  it("adds the municipality only when it is known", () => {
    expect(scopedBillQuery({ periferiaId: 6, dimosId: 22 })).toEqual({
      periferia_id: 6,
      dimos_id: 22,
      include_institutional: false,
    });
  });
});

describe("availableGeographicFilters", () => {
  it("does not expose foreign geographic feeds", () => {
    expect(availableGeographicFilters({ periferiaId: null, dimosId: null })).toEqual([]);
    expect(availableGeographicFilters({ periferiaId: 6, dimosId: null })).toEqual(["REGIONAL"]);
    expect(availableGeographicFilters({ periferiaId: 6, dimosId: 22 })).toEqual(["REGIONAL", "MUNICIPAL"]);
  });
});
