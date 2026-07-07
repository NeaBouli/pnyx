import { afterEach, describe, expect, it, vi } from "vitest";
import {
  buildBillsQuery,
  fetchZkRoot,
  fetchZkRootMembers,
  submitZkOptIn,
  submitZkVote,
  verifyZkProof,
} from "./api";

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

  it("supports multi-status filtering for the Active tab", () => {
    expect(buildBillsQuery({
      limit: 10,
      offset: 0,
      status_any: "ACTIVE,WINDOW_24H",
    })).toBe("limit=10&offset=0&status_any=ACTIVE%2CWINDOW_24H");
  });

  it("can exclude institutional Diavgeia from the mixed All feed", () => {
    expect(buildBillsQuery({
      limit: 20,
      offset: 0,
      periferia_id: 1,
      dimos_id: 2,
      include_institutional: false,
    })).toBe("limit=20&offset=0&periferia_id=1&dimos_id=2&include_institutional=false");
  });
});

describe("ZK API helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("submits the backend ZK opt-in payload shape", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "accepted",
        vote_scope_id: "bill:ZK-CANARY-001",
        commitment_id: 7,
        tier_locked: true,
        merkle_tree_depth: 16,
        message_el: "ok",
      }),
    } as Response);

    await expect(submitZkOptIn({
      nullifierHash: "nullifier-1",
      billId: "ZK-CANARY-001",
      commitment: "123456",
      signatureHex: "abcdef",
    })).resolves.toMatchObject({ commitment_id: 7 });

    expect(fetchMock).toHaveBeenCalledWith("https://api.ekklesia.gr/api/v1/zk/opt-in", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        nullifier_hash: "nullifier-1",
        bill_id: "ZK-CANARY-001",
        commitment: "123456",
        signature_hex: "abcdef",
      }),
    }));
  });

  it("encodes root scope in the path", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        vote_scope_id: "bill:ZK-CANARY-001",
        merkle_root: "1",
        merkle_depth: 16,
        group_size: 1,
        commitment_version: "semaphore-v4",
        status: "OPEN",
        root_id: 3,
      }),
    } as Response);

    await fetchZkRoot("bill:ZK-CANARY-001");

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.ekklesia.gr/api/v1/zk/roots/bill%3AZK-CANARY-001",
      expect.any(Object),
    );
  });

  it("fetches public root members for mobile proof generation", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        vote_scope_id: "bill:ZK-CANARY-001",
        merkle_root: "1",
        merkle_depth: 16,
        group_size: 2,
        commitment_version: "semaphore-v4",
        status: "OPEN",
        root_id: 3,
        members: ["1", "2"],
      }),
    } as Response);

    await expect(fetchZkRootMembers("bill:ZK-CANARY-001")).resolves.toMatchObject({
      members: ["1", "2"],
      group_size: 2,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.ekklesia.gr/api/v1/zk/roots/bill%3AZK-CANARY-001/members",
      expect.any(Object),
    );
  });

  it("submits only the public ZK vote receipt payload", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        accepted: true,
        vote_scope_id: "bill:ZK-CANARY-001",
        receipt_id: 9,
        arweave_pending: true,
        merkle_tree_depth: 16,
        verifier_version: "py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
      }),
    } as Response);

    await submitZkVote({
      voteScopeId: "bill:ZK-CANARY-001",
      voteCommitment: "YES",
      proof: { merkle_tree_root: "1", semaphore_nullifier: "2" },
    });

    expect(fetchMock).toHaveBeenCalledWith("https://api.ekklesia.gr/api/v1/zk/vote", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        vote_scope_id: "bill:ZK-CANARY-001",
        vote_commitment: "YES",
        proof: { merkle_tree_root: "1", semaphore_nullifier: "2" },
      }),
    }));
  });

  it("verifies a public ZK proof without storing a vote", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        enabled: true,
        proof_verified: true,
        merkle_tree_depth: 16,
        verifier_version: "py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
      }),
    } as Response);

    await expect(verifyZkProof({
      voteScopeId: "bill:ZK-CANARY-001",
      proof: { merkleTreeRoot: "1", scope: "2" },
    })).resolves.toMatchObject({ proof_verified: true });

    expect(fetchMock).toHaveBeenCalledWith("https://api.ekklesia.gr/api/v1/zk/verify", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        proof: { merkleTreeRoot: "1", scope: "2" },
        vote_scope_id: "bill:ZK-CANARY-001",
      }),
    }));
  });
});
