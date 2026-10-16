// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";

const custody = vi.hoisted(() => ({ locked: false, sign: vi.fn(), vote: vi.fn() }));
vi.mock("@/lib/keystore", () => ({
  withSigner: async (submit: (signer: unknown) => Promise<unknown>) => {
    custody.locked = true;
    try { return await submit({ nullifier: "a".repeat(64), sign: custody.sign }); }
    finally { custody.locked = false; }
  },
}));
vi.mock("@/lib/api", () => ({ voteRelevance: custody.vote }));
import RelevanceButtons from "./RelevanceButtons";

afterEach(() => { vi.resetAllMocks(); vi.unstubAllGlobals(); });

it("keeps acquisition, signing and relevance submission inside the shared lock", async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const container = document.createElement("div");
  const root = createRoot(container);
  let finish!: () => void;
  custody.sign.mockImplementation(async () => { expect(custody.locked).toBe(true); return "signature"; });
  custody.vote.mockImplementation(() => {
    expect(custody.locked).toBe(true);
    return new Promise<void>((resolve) => { finish = resolve; });
  });
  try {
    await act(async () => root.render(createElement(RelevanceButtons, { billId: "GR-1", locale: "en" })));
    await act(async () => container.querySelector("button")!.click());
    expect(custody.sign).toHaveBeenCalledWith(`relevance:GR-1:1:${"a".repeat(64)}`);
    expect(custody.vote).toHaveBeenCalledWith("GR-1", 1, "a".repeat(64), "signature");
    expect(custody.locked).toBe(true);
    expect(container.querySelector("button")!.disabled).toBe(true);
    await act(async () => finish());
    expect(custody.locked).toBe(false);
    expect(container.textContent).toContain("+1");
  } finally { await act(async () => root.unmount()); }
});
