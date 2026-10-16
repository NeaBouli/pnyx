import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API_URL, submitSignedVote } from "./api";
import { bytesToHex, hexToBytes, signPayload, verifyVote } from "./crypto";
import { ed25519 } from "@noble/curves/ed25519.js";

const billId = "GR-9133/α";
const nullifier = "a".repeat(64);
const seed = "01".repeat(32);
const timestamp = 1_792_152_000_000;
const signer = {
  nullifier,
  publicKeyHex: bytesToHex(ed25519.getPublicKey(hexToBytes(seed))),
  custody: "legacy" as const,
  sign: vi.fn(async (payload: string) => signPayload(seed, payload)),
};
const fetchMock = vi.fn();

function response(body: object, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function status(hasVoted = true, corrected = false, state = "WINDOW_24H") {
  return response({
    bill_id: billId, status: state, has_voted: hasVoted,
    vote: hasVoted ? "YES" : null, is_correction: corrected,
    can_correct: hasVoted && !corrected && state === "WINDOW_24H",
  });
}

beforeEach(() => {
  vi.spyOn(Date, "now").mockReturnValue(timestamp);
  signer.sign.mockClear();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("signed vote endpoint selection", () => {
  it.each([
    [false, false, "WINDOW_24H", "NO", false],
    [false, false, "ACTIVE", "YES", false],
    [true, false, "ACTIVE", "NO", false],
    [true, false, "WINDOW_24H", "YES", false],
    [true, true, "WINDOW_24H", "YES", false],
    [true, false, "WINDOW_24H", "NO", true],
    [true, true, "WINDOW_24H", "NO", true],
  ])("hasVote=%s corrected=%s state=%s choice=%s correction=%s", async (
    hasVoted, corrected, state, choice, isCorrection,
  ) => {
    fetchMock.mockResolvedValueOnce(status(hasVoted, corrected, state))
      .mockResolvedValueOnce(response({ success: true }));
    const result = await submitSignedVote(billId, choice, signer);
    expect(result.isCorrection).toBe(isCorrection);
    expect(result.response.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [statusUrl, statusInit] = fetchMock.mock.calls[0];
    expect(statusUrl).toBe(`${API_URL}/api/v1/vote/${encodeURIComponent(billId)}/status`);
    expect(statusInit).toMatchObject({ method: "POST", cache: "no-store" });
    const auth = JSON.parse(statusInit.body);
    expect(auth).toEqual({
      nullifier_hash: nullifier, timestamp_ms: timestamp,
      signature_hex: signPayload(seed, `vote-status-read:v1:${JSON.stringify([billId, nullifier, timestamp])}`),
    });
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe(isCorrection
      ? `${API_URL}/api/v1/vote/${encodeURIComponent(billId)}/correct`
      : `${API_URL}/api/v1/vote`);
    expect(init.method).toBe(isCorrection ? "PUT" : "POST");
    const payload = JSON.parse(init.body);
    expect(payload).toMatchObject({ bill_id: billId, vote: choice, nullifier_hash: nullifier });
    expect(verifyVote(signer.publicKeyHex, payload, payload.signature_hex)).toBe(true);
  });

  it("preserves /correct's 409 for the already-corrected UI", async () => {
    fetchMock.mockResolvedValueOnce(status(true, true))
      .mockResolvedValueOnce(response({ detail: "Η διόρθωση έχει ήδη χρησιμοποιηθεί" }, 409));
    const result = await submitSignedVote(billId, "no", signer);
    expect(result.isCorrection).toBe(true);
    expect(result.response.status).toBe(409);
    expect(await result.response.json()).toEqual({ detail: "Η διόρθωση έχει ήδη χρησιμοποιηθεί" });
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).vote).toBe("NO");
  });

  it("retries a lost correction response through POST when that choice is now stored", async () => {
    fetchMock.mockResolvedValueOnce(status())
      .mockRejectedValueOnce(new Error("Response lost"));
    await expect(submitSignedVote(billId, "NO", signer)).rejects.toThrow("Response lost");
    fetchMock.mockResolvedValueOnce(response({
      status: "WINDOW_24H", has_voted: true, vote: "NO", is_correction: true, can_correct: false,
    })).mockResolvedValueOnce(response({ success: true }));
    expect((await submitSignedVote(billId, "NO", signer)).isCorrection).toBe(false);
    expect(fetchMock.mock.calls.map(([, init]) => init.method)).toEqual(["POST", "PUT", "POST", "POST"]);
  });

  it("does not write when the signed status read fails", async () => {
    fetchMock.mockResolvedValueOnce(response({ detail: "Invalid signature" }, 401));
    const result = await submitSignedVote(billId, "NO", signer);
    expect(result.response.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(signer.sign).toHaveBeenCalledTimes(1);
  });
});
