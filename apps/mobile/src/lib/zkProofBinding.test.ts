import { describe, expect, it } from "vitest";

import {
  canonicalZkMessageValue,
  canonicalZkScopeValue,
  semaphoreTextToBigIntString,
} from "./zkProofBinding";

describe("zkProofBinding", () => {
  it("matches the S10 fixture text-to-BigInt values", () => {
    expect(semaphoreTextToBigIntString("ekklesia-zk-v2-self-test")).toBe(
      "45873391752058558044601404579209674360496649398805557534553359251228204204032",
    );
    expect(semaphoreTextToBigIntString("ekklesia-gh81-device-proof-check")).toBe(
      "45873391752058558044599583634004129577505356553759386758719768327808736387947",
    );
  });

  it("uses deterministic distinct canonical scope/message values", () => {
    const scope = canonicalZkScopeValue("bill:ZK-CANARY-001");
    const yes = canonicalZkMessageValue("bill:ZK-CANARY-001", "YES");
    const no = canonicalZkMessageValue("bill:ZK-CANARY-001", "NO");
    const otherScopeYes = canonicalZkMessageValue("bill:GR-0490a766", "YES");

    expect(scope).toMatch(/^[0-9]+$/);
    expect(yes).toMatch(/^[0-9]+$/);
    expect(yes).not.toBe(no);
    expect(yes).not.toBe(otherScopeYes);
  });

  it("matches the cross-platform canonical binding golden vector", () => {
    expect(canonicalZkScopeValue("bill:ZK-CANARY-001")).toBe(
      "370914005589917494686899888002103101308908263382419550513130591364723151628",
    );
    expect(canonicalZkMessageValue("bill:ZK-CANARY-001", "YES")).toBe(
      "407070568861162468786934533009590942791872866516897520794260496866694851506",
    );
  });

  it("rejects invalid scope and overlong direct text", () => {
    expect(() => canonicalZkScopeValue("bad")).toThrow("invalid vote_scope_id");
    expect(() => semaphoreTextToBigIntString("x".repeat(33))).toThrow(
      "Semaphore text BigInt input must be 1..32 UTF-8 bytes",
    );
  });
});
