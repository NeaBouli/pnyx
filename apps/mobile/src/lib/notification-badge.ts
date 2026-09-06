import { nextBadgeCount } from "./notification-preferences";

export type BadgeAdapter = {
  getBadgeCountAsync: () => Promise<number>;
  setBadgeCountAsync: (count: number) => Promise<boolean>;
};

type EnabledReader = () => Promise<boolean>;

export function isNotificationResponsePayload(payload: unknown): boolean {
  return (
    !!payload &&
    typeof payload === "object" &&
    typeof (payload as { actionIdentifier?: unknown }).actionIdentifier ===
      "string"
  );
}

export function createNotificationBadgeQueue() {
  let operation: Promise<void> = Promise.resolve();

  return {
    incrementWhenEnabled(
      adapter: BadgeAdapter,
      isStillEnabled: EnabledReader,
    ): Promise<void> {
      operation = operation
        .catch(() => {})
        .then(async () => {
          if (!(await isStillEnabled())) return;
          const current = await adapter.getBadgeCountAsync();
          await adapter.setBadgeCountAsync(nextBadgeCount(current));
        });
      return operation;
    },

    clear(adapter: BadgeAdapter): Promise<void> {
      operation = operation
        .catch(() => {})
        .then(async () => {
          await adapter.setBadgeCountAsync(0);
        });
      return operation;
    },

    set(adapter: BadgeAdapter, count: number | (() => Promise<number>)): Promise<void> {
      operation = operation
        .catch(() => {})
        .then(async () => {
          const current = typeof count === "function" ? await count() : count;
          const normalized =
            Number.isFinite(current) && current > 0 ? Math.floor(current) : 0;
          await adapter.setBadgeCountAsync(Math.min(normalized, 99));
        });
      return operation;
    },
  };
}
