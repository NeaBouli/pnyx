import * as LocalAuthentication from "expo-local-authentication";
import * as SecureStore from "expo-secure-store";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { confirmOnDevice, confirmRegularVote, isVoteDeviceConfirmationEnabled, saveVoteDeviceConfirmation } from "./vote-device-confirmation";

vi.mock("expo-local-authentication", () => ({
  SecurityLevel: { NONE: 0, SECRET: 1, BIOMETRIC_STRONG: 3 },
  authenticateAsync: vi.fn(),
  getEnrolledLevelAsync: vi.fn(),
}));
vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn(),
  setItemAsync: vi.fn(),
}));

const authenticate = vi.mocked(LocalAuthentication.authenticateAsync);
const enrolledLevel = vi.mocked(LocalAuthentication.getEnrolledLevelAsync);
const read = vi.mocked(SecureStore.getItemAsync);
const write = vi.mocked(SecureStore.setItemAsync);

beforeEach(() => {
  vi.resetAllMocks();
  const storage = new Map<string, string>();
  read.mockImplementation(async key => storage.get(key) ?? null);
  write.mockImplementation(async (key, value) => { storage.set(key, value); });
  enrolledLevel.mockResolvedValue(LocalAuthentication.SecurityLevel.SECRET);
});

describe("regular vote device confirmation", () => {
  it.each(["not_enrolled", "passcode_not_set"] as const)("allows an unset preference on a device without a lock (%s)", async error => {
    authenticate.mockResolvedValue({ success: false, error });
    enrolledLevel.mockResolvedValue(LocalAuthentication.SecurityLevel.NONE);
    expect(await isVoteDeviceConfirmationEnabled("owner-a")).toBe(false);
    expect(await confirmRegularVote("owner-a")).toBe("allowed");
  });

  it("allows the device credential prompt for a protected device", async () => {
    authenticate.mockResolvedValue({ success: true });
    expect(await isVoteDeviceConfirmationEnabled("owner-a")).toBe(true);
    expect(await confirmRegularVote("owner-a")).toBe("allowed");
    expect(authenticate).toHaveBeenCalledWith(expect.objectContaining({ disableDeviceFallback: false }));
  });

  it("uses the saved opt-out only for its local identity", async () => {
    await saveVoteDeviceConfirmation("owner-a", false);
    expect(write.mock.calls[0][0]).not.toContain("owner-a");
    expect(await isVoteDeviceConfirmationEnabled("owner-a")).toBe(false);
    expect(await confirmRegularVote("owner-a")).toBe("allowed");
    expect(authenticate).not.toHaveBeenCalled();
    authenticate.mockResolvedValue({ success: false, error: "user_cancel" });
    expect(await isVoteDeviceConfirmationEnabled("owner-b")).toBe(true);
    expect(await confirmRegularVote("owner-b")).toBe("denied");
  });

  it("honors an explicit opt-in when the device lock has been removed", async () => {
    await saveVoteDeviceConfirmation("owner-a", true);
    authenticate.mockResolvedValue({ success: false, error: "not_enrolled" });
    enrolledLevel.mockResolvedValue(LocalAuthentication.SecurityLevel.NONE);
    expect(await isVoteDeviceConfirmationEnabled("owner-a")).toBe(true);
    expect(await confirmRegularVote("owner-a")).toBe("no_lock");
  });

  it("does not bypass an enrollment error when a PIN is still enrolled", async () => {
    authenticate.mockResolvedValue({ success: false, error: "not_enrolled" });
    expect(await confirmRegularVote("owner-a")).toBe("denied");
  });

  it.each(["user_cancel", "lockout", "not_available"] as const)("does not bypass %s", async error => {
    authenticate.mockResolvedValue({ success: false, error });
    enrolledLevel.mockResolvedValue(LocalAuthentication.SecurityLevel.NONE);
    expect(await confirmRegularVote("owner-a")).toBe("denied");
    expect(enrolledLevel).not.toHaveBeenCalled();
  });

  it("denies on a native error and preserves protection on a storage error", async () => {
    authenticate.mockRejectedValueOnce(new Error("native failure"));
    expect(await confirmOnDevice("Confirm")).toBe("denied");
    read.mockRejectedValueOnce(new Error("storage failure"));
    authenticate.mockResolvedValue({ success: false, error: "not_enrolled" });
    enrolledLevel.mockResolvedValue(LocalAuthentication.SecurityLevel.NONE);
    expect(await confirmRegularVote("owner-a")).toBe("no_lock");
  });
});
