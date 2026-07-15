import { describe, expect, it } from "vitest";
import { consensusScoreLabel, unavailableViewMessage } from "./consensus-results";
import type { ConsensusRepresentationView } from "./api";

function view(available: boolean): ConsensusRepresentationView {
  return {
    view: "municipal",
    available,
    bill_count: 0,
    consensus_vote_count: 0,
    weighted_score: null,
    bills: [],
  };
}

describe("DIAVGEIA consensus result helpers", () => {
  it("describes the whole -5 to +5 scale", () => {
    expect(consensusScoreLabel(4)).toBe("Ισχυρή συναίνεση");
    expect(consensusScoreLabel(1)).toBe("Θετική τάση");
    expect(consensusScoreLabel(0)).toBe("Ουδέτερη τάση");
    expect(consensusScoreLabel(-1)).toBe("Αρνητική τάση");
    expect(consensusScoreLabel(-4)).toBe("Ισχυρή διαφωνία");
  });

  it("distinguishes missing location from an empty result set", () => {
    expect(unavailableViewMessage(view(false))).toContain("Δήμο");
    expect(unavailableViewMessage(view(true))).toBeNull();
  });
});
