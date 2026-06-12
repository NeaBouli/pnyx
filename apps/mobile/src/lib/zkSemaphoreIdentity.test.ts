import { beforeEach, describe, expect, it, vi } from "vitest";

const secureStore = vi.hoisted(() => new Map<string, string>());

vi.mock("expo-crypto", () => ({
  getRandomBytes: vi.fn((length: number) => Uint8Array.from({ length }, (_, index) => index + 1)),
}));

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn((key: string) => Promise.resolve(secureStore.get(key) ?? null)),
  setItemAsync: vi.fn((key: string, value: string) => {
    secureStore.set(key, value);
    return Promise.resolve();
  }),
  deleteItemAsync: vi.fn((key: string) => {
    secureStore.delete(key);
    return Promise.resolve();
  }),
}));

vi.mock("semaphore-react-native", () => ({
  Identity: class FakeIdentity {
    constructor(private readonly privateKey: Uint8Array) {}

    commitment(): string {
      return `commitment-${this.privateKey[0]}`;
    }

    toElement(): Uint8Array {
      return Uint8Array.from([this.privateKey[0], this.privateKey[1], this.privateKey[2]]);
    }
  },
}));

import { bytesToHex } from "./crypto-native";
import {
  clearZkSemaphoreIdentity,
  getOrCreateZkSemaphoreIdentity,
  getOrCreateZkSemaphorePrivateKey,
} from "./zkSemaphoreIdentity";

describe("zkSemaphoreIdentity", () => {
  beforeEach(() => {
    secureStore.clear();
  });

  it("creates and reuses a separate Semaphore private key", async () => {
    const first = await getOrCreateZkSemaphorePrivateKey();
    const second = await getOrCreateZkSemaphorePrivateKey();

    expect(bytesToHex(first)).toBe("0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20");
    expect(bytesToHex(second)).toBe(bytesToHex(first));
    expect(secureStore.has("ekklesia_zk_semaphore_private_key_v1")).toBe(true);
  });

  it("exposes only the commitment/member representation for opt-in", async () => {
    const identity = await getOrCreateZkSemaphoreIdentity();

    expect(identity.commitment).toBe("commitment-1");
    expect(identity.memberHex).toBe("010203");
    expect(identity.privateKey).toBeInstanceOf(Uint8Array);
  });

  it("can clear the ZK identity without touching other keys", async () => {
    secureStore.set("ekklesia_private_key", "tier1");
    await getOrCreateZkSemaphorePrivateKey();

    await clearZkSemaphoreIdentity();

    expect(secureStore.has("ekklesia_zk_semaphore_private_key_v1")).toBe(false);
    expect(secureStore.get("ekklesia_private_key")).toBe("tier1");
  });
});
