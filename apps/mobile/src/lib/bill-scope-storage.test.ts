import { beforeEach, describe, expect, it, vi } from "vitest";

const secureStore = vi.hoisted(() => ({
  getItemAsync: vi.fn(),
  setItemAsync: vi.fn(),
  deleteItemAsync: vi.fn(),
}));
const api = vi.hoisted(() => ({ checkIdentityStatus: vi.fn() }));

vi.mock("expo-secure-store", () => secureStore);
vi.mock("./api", () => api);

import { loadUserBillScope } from "./bill-scope-storage";

describe("loadUserBillScope", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    secureStore.getItemAsync.mockResolvedValue(null);
    secureStore.setItemAsync.mockResolvedValue(undefined);
    secureStore.deleteItemAsync.mockResolvedValue(undefined);
  });

  it("uses and caches the active canonical server identity as authoritative", async () => {
    secureStore.getItemAsync.mockImplementation(async (key: string) => ({
      user_periferia_id: "7",
      user_dimos_id: "99",
      ekklesia_nullifier: "n".repeat(64),
    }[key] ?? null));
    api.checkIdentityStatus.mockResolvedValue({
      status: "ACTIVE",
      periferia_id: 6,
      dimos_id: 22,
    });

    await expect(loadUserBillScope()).resolves.toEqual({ periferiaId: 6, dimosId: 22 });
    expect(secureStore.setItemAsync).toHaveBeenCalledWith("user_periferia_id", "6");
    expect(secureStore.setItemAsync).toHaveBeenCalledWith("user_dimos_id", "22");
  });

  it("never reads an invalid legacy SecureStore key", async () => {
    const canonical = "c".repeat(64);
    secureStore.getItemAsync.mockImplementation(async (key: string) => {
      if (key.includes(":")) throw new Error("invalid SecureStore key");
      return key === "ekklesia_nullifier" ? canonical : null;
    });
    api.checkIdentityStatus.mockResolvedValue({
      status: "ACTIVE",
      periferia_id: 2,
      dimos_id: 18,
    });

    await expect(loadUserBillScope()).resolves.toEqual({ periferiaId: 2, dimosId: 18 });
    expect(api.checkIdentityStatus).toHaveBeenCalledWith(canonical);
    expect(secureStore.setItemAsync).toHaveBeenCalledWith("user_bill_scope_owner", canonical);
    expect(secureStore.getItemAsync).not.toHaveBeenCalledWith("ekklesia:nullifier:v1");
  });

  it.each(["user_periferia_id", "user_dimos_id", "user_bill_scope_owner"])(
    "keeps an active authoritative server scope when caching %s fails",
    async (failingKey) => {
    const canonical = "c".repeat(64);
    secureStore.getItemAsync.mockImplementation(async (key: string) => ({
      "ekklesia_nullifier": canonical,
    }[key] ?? null));
    api.checkIdentityStatus.mockResolvedValue({
      status: "ACTIVE",
      periferia_id: 6,
      dimos_id: 22,
    });
    secureStore.setItemAsync.mockImplementation(async (key: string) => {
      if (key === failingKey) throw new Error("secure storage unavailable");
    });

    await expect(loadUserBillScope()).resolves.toEqual({ periferiaId: 6, dimosId: 22 });
    },
  );

  it("fails closed when the identity is not active", async () => {
    secureStore.getItemAsync.mockImplementation(async (key: string) => ({
      user_periferia_id: "6",
      user_dimos_id: "22",
      user_bill_scope_owner: "n".repeat(64),
      ekklesia_nullifier: "n".repeat(64),
    }[key] ?? null));
    api.checkIdentityStatus.mockResolvedValue({ status: "REVOKED" });

    await expect(loadUserBillScope()).resolves.toEqual({ periferiaId: null, dimosId: null });
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith("user_bill_scope_owner");
  });

  it("keeps the last cached read scope only while the primary is unavailable", async () => {
    secureStore.getItemAsync.mockImplementation(async (key: string) => {
      if (key.includes(":")) throw new Error("invalid SecureStore key");
      return ({
        user_periferia_id: "6",
        user_dimos_id: "22",
        user_bill_scope_owner: "n".repeat(64),
        ekklesia_nullifier: "n".repeat(64),
      }[key] ?? null);
    });
    api.checkIdentityStatus.mockRejectedValue(new Error("offline"));

    await expect(loadUserBillScope()).resolves.toEqual({ periferiaId: 6, dimosId: 22 });
    expect(secureStore.getItemAsync).not.toHaveBeenCalledWith("ekklesia:nullifier:v1");
  });

  it("rejects an offline cache owned by another identity", async () => {
    secureStore.getItemAsync.mockImplementation(async (key: string) => ({
      user_periferia_id: "6",
      user_dimos_id: "22",
      user_bill_scope_owner: "old-identity",
      ekklesia_nullifier: "n".repeat(64),
    }[key] ?? null));
    api.checkIdentityStatus.mockRejectedValue(new Error("offline"));

    await expect(loadUserBillScope()).resolves.toEqual({ periferiaId: null, dimosId: null });
  });

  it("clears an old geographic cache when no active identity exists", async () => {
    secureStore.getItemAsync.mockImplementation(async (key: string) => ({
      user_periferia_id: "6",
      user_dimos_id: "22",
      user_bill_scope_owner: "old-identity",
    }[key] ?? null));

    await expect(loadUserBillScope()).resolves.toEqual({ periferiaId: null, dimosId: null });
    expect(api.checkIdentityStatus).not.toHaveBeenCalled();
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith("user_periferia_id");
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith("user_dimos_id");
    expect(secureStore.deleteItemAsync).toHaveBeenCalledWith("user_bill_scope_owner");
    expect(secureStore.deleteItemAsync).not.toHaveBeenCalledWith("pending_user_periferia_id");
    expect(secureStore.deleteItemAsync).not.toHaveBeenCalledWith("pending_user_dimos_id");
  });
});
