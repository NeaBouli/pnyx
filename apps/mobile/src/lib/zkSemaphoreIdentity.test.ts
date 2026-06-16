import { beforeEach, describe, expect, it, vi } from "vitest";

const secureStore = vi.hoisted(() => new Map<string, string>());
const cryptoState = vi.hoisted(() => ({ calls: 0 }));

vi.mock("expo-crypto", () => ({
  getRandomBytes: vi.fn((length: number) => {
    const offset = cryptoState.calls * length;
    cryptoState.calls += 1;
    return Uint8Array.from({ length }, (_, index) => ((offset + index + 1) % 256));
  }),
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
    cryptoState.calls = 0;
  });

  it("creates and reuses a separate Semaphore private key", async () => {
    const first = await getOrCreateZkSemaphorePrivateKey();
    const second = await getOrCreateZkSemaphorePrivateKey();

    expect(bytesToHex(first)).toBe("0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20");
    expect(bytesToHex(second)).toBe(bytesToHex(first));
    expect(secureStore.has("ekklesia_zk_semaphore_private_key_v1")).toBe(true);
  });

  it("separates Semaphore private keys per vote scope", async () => {
    const first = await getOrCreateZkSemaphorePrivateKey("bill:GR-1");
    const second = await getOrCreateZkSemaphorePrivateKey("bill:GR-2");
    const firstAgain = await getOrCreateZkSemaphorePrivateKey("bill:GR-1");

    expect(bytesToHex(first)).toBe("0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20");
    expect(bytesToHex(second)).not.toBe(bytesToHex(first));
    expect(bytesToHex(firstAgain)).toBe(bytesToHex(first));
    expect(secureStore.has("ekklesia_zk_semaphore_private_key_v1:bill_GR-1")).toBe(true);
    expect(secureStore.has("ekklesia_zk_semaphore_private_key_v1:bill_GR-2")).toBe(true);
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

  it("can clear only one scoped ZK identity", async () => {
    await getOrCreateZkSemaphorePrivateKey("bill:GR-1");
    await getOrCreateZkSemaphorePrivateKey("bill:GR-2");

    await clearZkSemaphoreIdentity("bill:GR-1");

    expect(secureStore.has("ekklesia_zk_semaphore_private_key_v1:bill_GR-1")).toBe(false);
    expect(secureStore.has("ekklesia_zk_semaphore_private_key_v1:bill_GR-2")).toBe(true);
  });
});
