import { beforeEach, describe, expect, it, vi } from "vitest";

const secureStore = vi.hoisted(() => ({
  getItemAsync: vi.fn(),
  setItemAsync: vi.fn(),
  deleteItemAsync: vi.fn(),
}));
const api = vi.hoisted(() => ({ updateIdentityLocation: vi.fn() }));
const crypto = vi.hoisted(() => ({ signProfileLocation: vi.fn() }));

vi.mock("expo-secure-store", () => secureStore);
vi.mock("./api", () => api);
vi.mock("./crypto-native", () => crypto);

import {
  clearPendingProfileLocation,
  loadPendingProfileLocation,
  loadStoredProfileLocation,
  storeProfileLocation,
  syncProfileLocation,
} from "./profile-location";

describe("profile location synchronization", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    secureStore.getItemAsync.mockResolvedValue(null);
    secureStore.setItemAsync.mockResolvedValue(undefined);
    secureStore.deleteItemAsync.mockResolvedValue(undefined);
    crypto.signProfileLocation.mockReturnValue("signed");
  });

  it("loads only positive pending IDs before verification", async () => {
    secureStore.getItemAsync.mockImplementation(async (key: string) => ({
      pending_user_periferia_id: "6",
      pending_user_dimos_id: "invalid",
    }[key] ?? null));

    await expect(loadPendingProfileLocation()).resolves.toEqual({
      periferiaId: 6,
      dimosId: null,
    });
  });

  it("loads a server-confirmed scope only for its owning identity", async () => {
    secureStore.getItemAsync.mockImplementation(async (key: string) => ({
      user_periferia_id: "6",
      user_dimos_id: "22",
      user_bill_scope_owner: "current-identity",
    }[key] ?? null));

    await expect(loadStoredProfileLocation("current-identity")).resolves.toEqual({
      periferiaId: 6,
      dimosId: 22,
    });
  });

  it("rejects a geographic cache owned by another identity", async () => {
    secureStore.getItemAsync.mockImplementation(async (key: string) => ({
      user_periferia_id: "6",
      user_dimos_id: "22",
      user_bill_scope_owner: "previous-identity",
      pending_user_periferia_id: "7",
      pending_user_dimos_id: "33",
    }[key] ?? null));

    await expect(loadStoredProfileLocation("current-identity")).resolves.toEqual({
      periferiaId: null,
      dimosId: null,
    });
  });

  it("never falls back from a pending selection to another identity's scope", async () => {
    secureStore.getItemAsync.mockImplementation(async (key: string) => ({
      user_periferia_id: "6",
      user_dimos_id: "22",
      user_bill_scope_owner: "previous-identity",
    }[key] ?? null));

    await expect(loadPendingProfileLocation()).resolves.toEqual({
      periferiaId: null,
      dimosId: null,
    });
  });

  it("discards all unverified location state before a new identity can use it", async () => {
    await clearPendingProfileLocation();

    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith("pending_user_periferia_id");
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith("pending_user_dimos_id");
    expect(secureStore.deleteItemAsync).not.toHaveBeenCalledWith("user_periferia_id");
    expect(secureStore.deleteItemAsync).not.toHaveBeenCalledWith("user_dimos_id");
  });

  it("removes empty values instead of caching zero", async () => {
    await storeProfileLocation({ periferiaId: 0, dimosId: null });

    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith("pending_user_periferia_id");
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith("pending_user_dimos_id");
  });

  it("keeps an unverified selection separate from an identity-bound cache", async () => {
    await storeProfileLocation({ periferiaId: 6, dimosId: 22 });

    expect(secureStore.setItemAsync).toHaveBeenCalledWith("pending_user_periferia_id", "6");
    expect(secureStore.setItemAsync).toHaveBeenCalledWith("pending_user_dimos_id", "22");
    expect(secureStore.setItemAsync).not.toHaveBeenCalledWith("user_periferia_id", "6");
    expect(secureStore.deleteItemAsync).not.toHaveBeenCalledWith("user_bill_scope_owner");
  });

  it("stores only the authoritative server response", async () => {
    api.updateIdentityLocation.mockResolvedValue({
      success: true,
      periferia_id: 6,
      dimos_id: 22,
      region_locked: true,
    });

    await syncProfileLocation({
      nullifierHash: "n".repeat(64),
      privateKeyHex: "a".repeat(64),
      selection: { periferiaId: null, dimosId: 22 },
    });

    expect(crypto.signProfileLocation).toHaveBeenCalledWith(
      "a".repeat(64), null, 22, "n".repeat(64),
    );
    expect(api.updateIdentityLocation).toHaveBeenCalledWith(expect.objectContaining({
      periferia_id: null,
      dimos_id: 22,
      signature_hex: "signed",
    }));
    expect(secureStore.setItemAsync).toHaveBeenCalledWith("user_periferia_id", "6");
    expect(secureStore.setItemAsync).toHaveBeenCalledWith("user_dimos_id", "22");
    expect(secureStore.setItemAsync).toHaveBeenCalledWith("user_bill_scope_owner", "n".repeat(64));
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith("pending_user_periferia_id");
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith("pending_user_dimos_id");
  });

  it("does not change local storage when the server rejects the request", async () => {
    api.updateIdentityLocation.mockRejectedValue(new Error("rejected"));

    await expect(syncProfileLocation({
      nullifierHash: "n".repeat(64),
      privateKeyHex: "a".repeat(64),
      selection: { periferiaId: 6, dimosId: 22 },
    })).rejects.toThrow("rejected");

    expect(secureStore.setItemAsync).not.toHaveBeenCalled();
    expect(secureStore.deleteItemAsync).not.toHaveBeenCalled();
  });
});
