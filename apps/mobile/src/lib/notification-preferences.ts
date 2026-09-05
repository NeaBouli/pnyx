export type NotificationPreferenceKey =
  | "push_vote_open"
  | "push_vote_24h"
  | "push_vote_result"
  | "push_bill_announced"
  | "push_weekly_digest"
  | "push_system_update";

type PreferenceReader = (key: string) => Promise<string | null>;

const TEMPLATE_PREFERENCES: Record<string, NotificationPreferenceKey> = {
  new_bill: "push_vote_open",
  vote_open: "push_vote_open",
  vote_24h: "push_vote_24h",
  result: "push_vote_result",
  vote_result: "push_vote_result",
  bill_announced: "push_bill_announced",
  weekly_digest: "push_weekly_digest",
  system_update: "push_system_update",
};

export function preferenceKeyForTemplate(
  templateId: unknown,
): NotificationPreferenceKey {
  if (typeof templateId !== "string") return "push_system_update";
  return TEMPLATE_PREFERENCES[templateId] ?? "push_system_update";
}

export async function isNotificationEnabled(
  readPreference: PreferenceReader,
  templateId: unknown,
): Promise<boolean> {
  const master = await readPreference("push_master");
  if (master === "false") return false;

  const category = preferenceKeyForTemplate(templateId);
  return (await readPreference(category)) !== "false";
}

export function nextBadgeCount(current: unknown): number {
  const normalized =
    typeof current === "number" && Number.isFinite(current) && current >= 0
      ? Math.floor(current)
      : 0;
  return Math.min(normalized + 1, 99);
}
