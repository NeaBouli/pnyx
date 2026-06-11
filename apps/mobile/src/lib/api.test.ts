import { describe, expect, it } from "vitest";
import { buildBillsQuery } from "./api";

describe("buildBillsQuery", () => {
  it("defaults to the previous broad limit when no pagination is requested", () => {
    expect(buildBillsQuery()).toBe("limit=200");
  });

  it("supports 10-item pagination with offset", () => {
    expect(buildBillsQuery({ limit: 10, offset: 20 })).toBe("limit=10&offset=20");
  });

  it("keeps server-side filters with pagination", () => {
    expect(buildBillsQuery({
      limit: 10,
      offset: 0,
      status: "ACTIVE",
      source: "DIAVGEIA",
      governance: "MUNICIPAL",
      periferia_id: 1,
      dimos_id: 2,
    })).toBe("limit=10&offset=0&status=ACTIVE&governance=MUNICIPAL&source=DIAVGEIA&periferia_id=1&dimos_id=2");
  });

  it("supports Parliament source filtering for the Bouli tab", () => {
    expect(buildBillsQuery({
      limit: 10,
      offset: 0,
      source: "PARLIAMENT",
    })).toBe("limit=10&offset=0&source=PARLIAMENT");
  });
});
