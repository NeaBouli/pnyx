import { describe, expect, it, vi } from "vitest";
import {
  isNotificationEnabled,
  nextBadgeCount,
  preferenceKeyForTemplate,
} from "./notification-preferences";

describe("notification preferences", () => {
  it("maps known push templates to their user-facing settings", () => {
    expect(preferenceKeyForTemplate("new_bill")).toBe("push_vote_open");
    expect(preferenceKeyForTemplate("vote_24h")).toBe("push_vote_24h");
    expect(preferenceKeyForTemplate("result")).toBe("push_vote_result");
    expect(preferenceKeyForTemplate("bill_announced")).toBe(
      "push_bill_announced",
    );
    expect(preferenceKeyForTemplate("weekly_digest")).toBe(
      "push_weekly_digest",
    );
  });

  it("routes unknown templates through the system-update preference", () => {
    expect(preferenceKeyForTemplate("future_template")).toBe(
      "push_system_update",
    );
    expect(preferenceKeyForTemplate(undefined)).toBe("push_system_update");
  });

  it("is fail-closed when the master switch is disabled", async () => {
    const read = vi.fn(async (key: string) =>
      key === "push_master" ? "false" : "true",
    );

    await expect(isNotificationEnabled(read, "new_bill")).resolves.toBe(false);
    expect(read).toHaveBeenCalledTimes(1);
  });

  it("honors category opt-outs and defaults unset preferences to enabled", async () => {
    const disabled = vi.fn(async (key: string) =>
      key === "push_vote_result" ? "false" : null,
    );
    const defaults = vi.fn(async () => null);

    await expect(isNotificationEnabled(disabled, "result")).resolves.toBe(
      false,
    );
    await expect(isNotificationEnabled(defaults, "new_bill")).resolves.toBe(
      true,
    );
  });

  it("increments valid counts and caps the launcher badge at 99", () => {
    expect(nextBadgeCount(0)).toBe(1);
    expect(nextBadgeCount(41.9)).toBe(42);
    expect(nextBadgeCount(99)).toBe(99);
    expect(nextBadgeCount(-1)).toBe(1);
    expect(nextBadgeCount("4")).toBe(1);
  });
});
