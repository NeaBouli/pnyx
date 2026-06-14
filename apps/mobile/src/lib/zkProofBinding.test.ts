import { describe, expect, it } from "vitest";

import {
  canonicalZkMessageText,
  canonicalZkMessageValue,
  canonicalZkScopeText,
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
    const scopeText = canonicalZkScopeText("bill:ZK-CANARY-001");
    const yesText = canonicalZkMessageText("bill:ZK-CANARY-001", "YES");
    const scope = canonicalZkScopeValue("bill:ZK-CANARY-001");
    const yes = canonicalZkMessageValue("bill:ZK-CANARY-001", "YES");
    const no = canonicalZkMessageValue("bill:ZK-CANARY-001", "NO");
    const otherScopeYes = canonicalZkMessageValue("bill:GR-0490a766", "YES");

    expect(new TextEncoder().encode(scopeText).length).toBeLessThanOrEqual(32);
    expect(new TextEncoder().encode(yesText).length).toBeLessThanOrEqual(32);
    expect(scopeText).toMatch(/^zks:[A-Za-z0-9_-]{28}$/);
    expect(yesText).toMatch(/^zkm:[A-Za-z0-9_-]{28}$/);
    expect(scope).toMatch(/^[0-9]+$/);
    expect(yes).toMatch(/^[0-9]+$/);
    expect(yes).not.toBe(no);
    expect(yes).not.toBe(otherScopeYes);
  });

  it("matches the cross-platform canonical binding golden vector", () => {
    expect(canonicalZkScopeText("bill:ZK-CANARY-001")).toBe(
      "zks:0e4NG-4g8ttGB4S3oNnvrvmirLeN",
    );
    expect(canonicalZkMessageText("bill:ZK-CANARY-001", "YES")).toBe(
      "zkm:5mTOk-0X_3vcqb8k_khYt92TxVfV",
    );
    expect(canonicalZkScopeValue("bill:ZK-CANARY-001")).toBe(
      "55372015432693197156684210389612366682933503607061176685521685831438937384270",
    );
    expect(canonicalZkMessageValue("bill:ZK-CANARY-001", "YES")).toBe(
      "55371974022745020309936148062986343275232691383944616415973239990294343476822",
    );
  });

  it("rejects invalid scope and overlong direct text", () => {
    expect(() => canonicalZkScopeValue("bad")).toThrow("invalid vote_scope_id");
    expect(() => semaphoreTextToBigIntString("x".repeat(33))).toThrow(
      "Semaphore text BigInt input must be 1..32 UTF-8 bytes",
    );
  });
});
