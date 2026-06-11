import { describe, expect, it } from "vitest";
import { mergeBillsUnique } from "./bill-feed";

describe("mergeBillsUnique", () => {
  it("keeps Parliament bills visible first in the mixed All feed", () => {
    const parliament = [
      { id: "GR-1", source: "PARLIAMENT" },
      { id: "GR-2", source: "PARLIAMENT" },
    ];
    const all = [
      { id: "DIAV-1", source: "DIAVGEIA" },
      { id: "GR-1", source: "PARLIAMENT" },
      { id: "DIAV-2", source: "DIAVGEIA" },
    ];

    expect(mergeBillsUnique(parliament, all, 4)).toEqual([
      { id: "GR-1", source: "PARLIAMENT" },
      { id: "GR-2", source: "PARLIAMENT" },
      { id: "DIAV-1", source: "DIAVGEIA" },
      { id: "DIAV-2", source: "DIAVGEIA" },
    ]);
  });

  it("respects the requested page size", () => {
    const parliament = [{ id: "GR-1" }, { id: "GR-2" }];
    const all = [{ id: "DIAV-1" }, { id: "DIAV-2" }, { id: "DIAV-3" }];

    expect(mergeBillsUnique(parliament, all, 3).map(b => b.id)).toEqual([
      "GR-1",
      "GR-2",
      "DIAV-1",
    ]);
  });
});
