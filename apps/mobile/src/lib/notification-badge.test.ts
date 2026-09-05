import { describe, expect, it, vi } from "vitest";
import {
  createNotificationBadgeQueue,
  isNotificationResponsePayload,
  type BadgeAdapter,
} from "./notification-badge";

function createAdapter(initial = 0) {
  let count = initial;
  const adapter: BadgeAdapter = {
    getBadgeCountAsync: vi.fn(async () => count),
    setBadgeCountAsync: vi.fn(async (next: number) => {
      count = next;
      return true;
    }),
  };
  return { adapter, getCount: () => count };
}

describe("notification badge queue", () => {
  it("distinguishes delivery payloads from notification taps", () => {
    expect(isNotificationResponsePayload({ template_id: "new_bill" })).toBe(
      false,
    );
    expect(
      isNotificationResponsePayload({
        actionIdentifier: "expo.modules.notifications.actions.DEFAULT",
      }),
    ).toBe(true);
  });

  it("serializes increments without losing notifications", async () => {
    const queue = createNotificationBadgeQueue();
    const { adapter, getCount } = createAdapter(4);

    await Promise.all([
      queue.incrementWhenEnabled(adapter, async () => true),
      queue.incrementWhenEnabled(adapter, async () => true),
    ]);

    expect(getCount()).toBe(6);
    expect(adapter.setBadgeCountAsync).toHaveBeenCalledTimes(2);
  });

  it("rechecks preferences inside the queue before incrementing", async () => {
    const queue = createNotificationBadgeQueue();
    const { adapter, getCount } = createAdapter(7);
    let enabled = true;

    const clear = queue.clear(adapter);
    enabled = false;
    const delayedIncrement = queue.incrementWhenEnabled(
      adapter,
      async () => enabled,
    );

    await Promise.all([clear, delayedIncrement]);

    expect(getCount()).toBe(0);
    expect(adapter.getBadgeCountAsync).not.toHaveBeenCalled();
    expect(adapter.setBadgeCountAsync).toHaveBeenCalledTimes(1);
  });

  it("continues after a launcher API failure", async () => {
    const queue = createNotificationBadgeQueue();
    const { adapter } = createAdapter();
    vi.mocked(adapter.setBadgeCountAsync)
      .mockRejectedValueOnce(new Error("launcher unavailable"))
      .mockImplementationOnce(async (next: number) => {
        return next === 1;
      });

    await expect(queue.clear(adapter)).rejects.toThrow("launcher unavailable");
    await expect(
      queue.incrementWhenEnabled(adapter, async () => true),
    ).resolves.toBeUndefined();
    expect(adapter.setBadgeCountAsync).toHaveBeenCalledTimes(2);
    expect(adapter.setBadgeCountAsync).toHaveBeenLastCalledWith(1);
  });
});
