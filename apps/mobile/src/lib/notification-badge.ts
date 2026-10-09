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

    /**
     * Set the absolute unread count. A count of 0 only reaches the native API
     * when `clearTray` is true (the user explicitly read the last event):
     * on Android expo-notifications implements setBadgeCountAsync(0) as
     * NotificationManager.cancelAll(), and One UI derives the icon number from
     * tray notifications. Automatic reconciles (app start, foreground, pushes,
     * duplicates, disabled categories) therefore never wipe the tray
     * (MOBILE-UX-20261007-01). getBadgeCountAsync() is not consulted: on
     * Android it is only an in-process value, not the tray or launcher state.
     */
    set(
      adapter: BadgeAdapter,
      count: number | (() => Promise<number>),
      options: { clearTray?: boolean } = {},
    ): Promise<void> {
      operation = operation
        .catch(() => {})
        .then(async () => {
          const current = typeof count === "function" ? await count() : count;
          const normalized =
            Number.isFinite(current) && current > 0 ? Math.floor(current) : 0;
          if (normalized === 0 && !options.clearTray) return;
          await adapter.setBadgeCountAsync(Math.min(normalized, 99));
        });
      return operation;
    },
  };
}
