import { describe, expect, it, vi } from "vitest";
import { CLOSE_LABEL, RESULTS_LABEL, voteSuccessDialog } from "./vote-success";

function nav(canGoBack = true) {
  return {
    canGoBack: vi.fn(() => canGoBack),
    goBack: vi.fn(),
    navigate: vi.fn(),
    replace: vi.fn(),
  };
}

const params = { billId: "GR-1", billTitle: "Νομοσχέδιο" };

describe("vote success dialog", () => {
  it("offers close first and results second", () => {
    const d = voteSuccessDialog(nav(), params);
    expect(d.buttons.map((b) => b.text)).toEqual([CLOSE_LABEL, RESULTS_LABEL]);
    expect(d.options.cancelable).toBe(true);
  });

  it("close returns to the previous screen", () => {
    const n = nav();
    voteSuccessDialog(n, params).buttons[0].onPress();
    expect(n.goBack).toHaveBeenCalledTimes(1);
    expect(n.replace).not.toHaveBeenCalled();
  });

  it("close falls back to the Bills tab without history", () => {
    const n = nav(false);
    voteSuccessDialog(n, params).buttons[0].onPress();
    expect(n.navigate).toHaveBeenCalledWith("Tabs", { screen: "Bills" });
  });

  it("results keeps the existing route and fromVote flag", () => {
    const n = nav();
    voteSuccessDialog(n, params).buttons[1].onPress();
    expect(n.replace).toHaveBeenCalledWith("Result", { billId: "GR-1", billTitle: "Νομοσχέδιο", fromVote: true });
  });

  it("android back / dismiss behaves like close", () => {
    const n = nav();
    voteSuccessDialog(n, params).options.onDismiss();
    expect(n.goBack).toHaveBeenCalledTimes(1);
  });

  it("navigates at most once however the dialog ends", () => {
    const n = nav();
    const d = voteSuccessDialog(n, params);
    d.buttons[1].onPress();
    d.options.onDismiss();
    d.buttons[0].onPress();
    expect(n.replace).toHaveBeenCalledTimes(1);
    expect(n.goBack).not.toHaveBeenCalled();
  });
});
