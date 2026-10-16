import { describe, expect, it } from "vitest";
import { publicVoteCount, publicVoteShare } from "./results-display";

describe("public result display", () => {
  it("labels a suppressed total with its threshold", () => {
    expect(publicVoteCount(null)).toBe("λιγότερες από 10 ψήφοι");
    expect(publicVoteCount(null, 20)).toBe("λιγότερες από 20 ψήφοι");
  });
  it("preserves exact public totals including zero when the flag is off", () => {
    expect(publicVoteCount(0)).toBe("0");
    expect(publicVoteCount(60)).toBe("60");
  });
  it("does not turn withheld counts or percentages into zero", () => {
    expect(publicVoteShare(null, null)).toBe("—");
    expect(publicVoteShare(60, null)).toBe("—");
    expect(publicVoteShare(null, 60)).toBe("—");
    expect(publicVoteShare(0, 0)).toBe("0 (0%)");
    expect(publicVoteShare(10, 25)).toBe("10 (25%)");
  });
});
