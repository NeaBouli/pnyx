import { afterEach, describe, expect, it, vi } from "vitest";
import {
  buildBillsQuery,
  fetchBills,
  getApiTransportState,
  resetApiTransportStateForTests,
  subscribeApiTransport,
  fetchVoteStatus,
  fetchZkRoot,
  fetchZkRootMembers,
  submitVote,
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
    resetApiTransportStateForTests();
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

describe("read-only mirror fallback", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("falls back to the mirror for public bill reads when primary is unavailable", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockRejectedValueOnce(new TypeError("Network request failed"))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([{
          id: "GR-1",
          title_el: "Τίτλος",
          pill_el: "Σύντομο",
          status: "ANNOUNCED",
          submitted_at: "2026-07-08T00:00:00Z",
          party_votes_parliament: null,
          relevance_score: 0,
        }]),
      } as Response);

    await expect(fetchBills({ limit: 1 })).resolves.toHaveLength(1);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://api.ekklesia.gr/api/v1/bills?limit=1",
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://mirror.204.168.165.143.nip.io/api/v1/bills?limit=1",
      expect.any(Object),
    );
    expect(getApiTransportState()).toEqual({
      mode: "mirror_readonly",
      mirrorUrl: "https://mirror.204.168.165.143.nip.io",
    });
  });

  it("falls back to the mirror for temporary primary server errors", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        statusText: "Service Unavailable",
        json: async () => ({ detail: "temporary" }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([]),
      } as Response);

    await expect(fetchBills({ limit: 1 })).resolves.toEqual([]);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][0]).toBe("https://mirror.204.168.165.143.nip.io/api/v1/bills?limit=1");
    expect(getApiTransportState().mode).toBe("mirror_readonly");
  });

  it("notifies subscribers when public reads switch to mirror read-only mode and back", async () => {
    const states: string[] = [];
    const unsubscribe = subscribeApiTransport((state) => states.push(state.mode));
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockRejectedValueOnce(new TypeError("Network request failed"))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([]),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([]),
      } as Response);

    await fetchBills({ limit: 1 });
    await fetchBills({ limit: 1 });
    unsubscribe();

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(states).toContain("mirror_readonly");
    expect(states.at(-1)).toBe("primary");
  });

  it("does not use the mirror for primary 404 responses", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: async () => ({ detail: "not found" }),
    } as Response);

    await expect(fetchBills({ limit: 1 })).rejects.toThrow("not found");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("https://api.ekklesia.gr/api/v1/bills?limit=1");
  });

  it("never falls back to the mirror for vote writes", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Network request failed"));

    await expect(submitVote("nullifier", "GR-1", "YES", "signature")).rejects.toThrow("Network request failed");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("https://api.ekklesia.gr/api/v1/vote");
  });

  it("does not mirror nullifier-bearing vote status reads", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Network request failed"));

    await expect(fetchVoteStatus("nullifier", "GR-1")).rejects.toThrow("Network request failed");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toContain("https://api.ekklesia.gr/api/v1/vote/GR-1/status");
  });
});
