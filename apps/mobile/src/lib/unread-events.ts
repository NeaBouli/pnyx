/**
 * unread-events.ts — Persistent per-event unread ledger (GH290)
 *
 * Replaces the blanket badge-clear on app start with a bounded, durable
 * ledger of notification events. Every event gets a stable, deterministic
 * ID so foreground delivery, background delivery and notification taps of
 * the same push deduplicate into a single entry, also across app restarts.
 *
 * - Unknown template IDs are invalid and dropped; they are never silently
 *   bucketed as system_update.
 * - Bill events derive their ID from the canonical template + bill_id
 *   (aliases new_bill/vote_open and result/vote_result are normalized).
 *   This canonical bill identity takes precedence over any explicit
 *   event_id, so pushes and the F-Droid foreground bill feed share IDs.
 *   Bill IDs allow Unicode letters/numbers plus `_` and `-` (covers Greek
 *   DIAV-* IDs such as DIAV-Ρ9Ζ546ΜΤΛΒ-Η) but never paths or URLs.
 * - Weekly/system events require an explicit stable event_id, version or
 *   date. There is no content-hash fallback; IDs are never random and
 *   never derived from receipt time. Events without a stable identity are
 *   dropped.
 * - Storage failures fail closed: a failed read rejects without caching an
 *   empty ledger, and a failed write leaves the cached state untouched so
 *   a retry persists.
 * - Read events and unread events evicted by the ledger bound are kept as
 *   bounded tombstones so replays stay deduplicated.
 * - Feed refreshes merge into the bounded prior snapshot (a partial feed
 *   never wipes it), treat a missing or malformed snapshot as a reseed
 *   baseline (no flood of historical bills), and save the snapshot only
 *   after every candidate was durably ingested into the ledger.
 * - Malformed persisted data is validated and dropped on load.
 *
 * Bounded memory horizon (accepted and intentional): the ledger holds at
 * most MAX_UNREAD_EVENTS unread events, MAX_READ_TOMBSTONES tombstones and
 * MAX_FEED_SNAPSHOT snapshot entries. Once a tombstone or snapshot entry
 * ages out beyond these bounds, a redelivery of that ancient event can be
 * re-notified once; the bounds make this window explicit instead of
 * growing storage without limit. All mutations run through a serialized
 * promise queue.
 */
import {
  isNotificationEnabled,
  preferenceKeyForTemplate,
  type NotificationPreferenceKey,
} from "./notification-preferences";

export const UNREAD_EVENTS_STORAGE_KEY = "unread_events_v1";
export const UNREAD_FEED_SNAPSHOT_KEY = "unread_feed_snapshot_v1";
export const MAX_UNREAD_EVENTS = 50;
export const MAX_READ_TOMBSTONES = 100;
export const MAX_FEED_SNAPSHOT = 500;
const MAX_TEXT_LENGTH = 120;
const MAX_ID_LENGTH = 160;

const CANONICAL_TEMPLATE: Record<string, string> = {
  new_bill: "vote_open",
  vote_open: "vote_open",
  vote_24h: "vote_24h",
  result: "vote_result",
  vote_result: "vote_result",
  bill_announced: "bill_announced",
  weekly_digest: "weekly_digest",
  system_update: "system_update",
};

const KNOWN_TEMPLATES = new Set([
  "vote_open",
  "vote_24h",
  "vote_result",
  "bill_announced",
  "weekly_digest",
  "system_update",
]);

/**
 * Feed status → event mapping for the foreground bill refresh. Mirrors the
 * API BillStatus enum (ANNOUNCED, ACTIVE, WINDOW_24H, PARLIAMENT_VOTED,
 * OPEN_END) exactly; OPEN_END is archival and produces no event. No
 * invented states.
 */
const FEED_STATUS_EVENTS: Record<string, { templateId: string; title: string }> = {
  ANNOUNCED: {
    templateId: "bill_announced",
    title: "🏛️ Νέο Νομοσχέδιο · New bill",
  },
  ACTIVE: {
    templateId: "vote_open",
    title: "🗳️ Νέα Ψηφοφορία · New vote",
  },
  WINDOW_24H: {
    templateId: "vote_24h",
    title: "⏰ Τελευταίες 24 Ώρες · Final 24 hours",
  },
  PARLIAMENT_VOTED: {
    templateId: "vote_result",
    title: "📊 Αποτέλεσμα · Result",
  },
};

export interface UnreadEvent {
  id: string;
  templateId: string;
  title: string;
  body: string;
  billId: string | null;
}

export type IngestResult = "added" | "duplicate" | "disabled" | "invalid";

export interface UnreadFeedRefresh {
  added: number;
  seeded: boolean;
}

interface LedgerState {
  events: UnreadEvent[];
  read: string[];
}

const EMPTY_STATE: LedgerState = { events: [], read: [] };

/**
 * Normalize a raw template alias to its canonical ID. Unknown or missing
 * templates return null so callers treat the event as invalid instead of
 * silently reclassifying it as a system update.
 */
export function canonicalTemplateId(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  return Object.prototype.hasOwnProperty.call(CANONICAL_TEMPLATE, raw)
    ? CANONICAL_TEMPLATE[raw] : null;
}

/**
 * Bill IDs routed to Vote/Result screens: Unicode letters/numbers plus `_`
 * and `-` (covers Greek DIAV-* IDs), never a path or URL — the charset
 * excludes `/`, `\`, `.`, `:` and whitespace by construction.
 */
const SAFE_BILL_ID = /^[\p{L}\p{N}_-]{1,64}$/u;
export function isSafeBillId(raw: unknown): raw is string {
  return typeof raw === "string" && SAFE_BILL_ID.test(raw);
}

function boundedIdPart(raw: unknown, max = 96): string | null {
  if (typeof raw === "number" && Number.isFinite(raw)) raw = String(raw);
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  if (!trimmed || trimmed.length > max) return null;
  return /^[A-Za-z0-9_.:-]+$/.test(trimmed) ? trimmed : null;
}

function truncateText(raw: unknown): string {
  if (typeof raw !== "string") return "";
  return raw.slice(0, MAX_TEXT_LENGTH);
}

/**
 * Derive a stable event ID from push/feed data. Bill events are keyed by
 * canonical template + bill_id, which takes precedence over any explicit
 * event_id. Weekly/system events require an explicit stable event_id,
 * version or date; there is no content-hash fallback and no receipt-time
 * or random component. Returns null when no stable ID can be formed (the
 * event is dropped as invalid).
 */
export function stableEventId(data: Record<string, unknown>): string | null {
  const template = canonicalTemplateId(data.template_id);
  if (!template) return null;

  if (isSafeBillId(data.bill_id)) return `${template}:${data.bill_id}`;

  const explicit = boundedIdPart(data.event_id);
  if (explicit) return `${template}:evt:${explicit}`;

  const version = boundedIdPart(data.version, 48);
  if (version) return `${template}:v:${version}`;

  const date = boundedIdPart(data.date, 48);
  if (date) return `${template}:d:${date}`;

  return null;
}

/**
 * Unwrap the data payload from the shapes expo-notifications delivers:
 * raw data, { data }, { data: { dataString } }, foreground notification
 * objects and tap responses ({ notification: { request: { content: { data } } } }).
 */
export function extractPushData(
  payload: unknown,
  depth = 2,
): Record<string, unknown> | null {
  if (!payload || typeof payload !== "object") return null;
  const record = payload as Record<string, unknown>;

  const notification = record.notification;
  if (notification && typeof notification === "object") {
    const inner = extractPushData(notification, depth);
    if (inner) return inner;
  }

  const request = record.request;
  if (request && typeof request === "object") {
    const content = (request as Record<string, unknown>).content;
    if (content && typeof content === "object") {
      const data = (content as Record<string, unknown>).data;
      if (data && typeof data === "object") {
        return extractPushData(data, depth) ?? (data as Record<string, unknown>);
      }
    }
  }

  let data: Record<string, unknown> | null = null;
  if (record.data && typeof record.data === "object") {
    data = record.data as Record<string, unknown>;
    const dataString = data.dataString;
    if (depth > 0 && typeof dataString === "string") {
      try {
        const inner = extractPushData(JSON.parse(dataString), depth - 1);
        if (inner) data = { ...data, ...inner };
      } catch {}
    }
  }
  if (data) return data;
  if (typeof record.template_id === "string") return record;
  return null;
}

function isValidEventId(id: unknown): id is string {
  return (
    typeof id === "string" &&
    id.length > 0 &&
    id.length <= MAX_ID_LENGTH &&
    /^[\p{L}\p{N}_.:-]+$/u.test(id)
  );
}

function sanitizeEvent(raw: unknown): UnreadEvent | null {
  if (!raw || typeof raw !== "object") return null;
  const record = raw as Record<string, unknown>;
  if (!isValidEventId(record.id)) return null;
  const templateId =
    typeof record.templateId === "string" && KNOWN_TEMPLATES.has(record.templateId)
      ? record.templateId
      : null;
  if (!templateId) return null;
  const billId = isSafeBillId(record.billId) ? record.billId : null;
  return {
    id: record.id,
    templateId,
    title: truncateText(record.title),
    body: truncateText(record.body),
    billId,
  };
}

/** Validate persisted ledger data; malformed input degrades to empty. */
export function parseUnreadLedger(raw: string | null): LedgerState {
  if (!raw) return { ...EMPTY_STATE, events: [], read: [] };
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { events: [], read: [] };
  }
  if (!parsed || typeof parsed !== "object") return { events: [], read: [] };
  const record = parsed as Record<string, unknown>;

  const readRaw = Array.isArray(record.read) ? record.read : [];
  const read: string[] = [];
  for (const id of readRaw) {
    if (isValidEventId(id) && !read.includes(id)) read.push(id);
    if (read.length >= MAX_READ_TOMBSTONES) break;
  }
  const readSet = new Set(read);

  const eventsRaw = Array.isArray(record.events) ? record.events : [];
  const events: UnreadEvent[] = [];
  const seen = new Set<string>();
  for (const candidate of eventsRaw) {
    const event = sanitizeEvent(candidate);
    if (!event || seen.has(event.id) || readSet.has(event.id)) continue;
    seen.add(event.id);
    events.push(event);
    if (events.length >= MAX_UNREAD_EVENTS) break;
  }
  return { events, read };
}

function serializeLedger(state: LedgerState): string {
  return JSON.stringify({ events: state.events, read: state.read });
}

/** Append IDs to the bounded tombstone list (deduplicated, oldest drop off). */
function withTombstones(read: string[], ids: string[]): string[] {
  if (ids.length === 0) return read;
  const tombstoned = new Set(read);
  const next = [...read];
  for (const id of ids) {
    if (!tombstoned.has(id)) {
      tombstoned.add(id);
      next.push(id);
    }
  }
  while (next.length > MAX_READ_TOMBSTONES) next.shift();
  return next;
}

type StorageGet = (key: string) => Promise<string | null>;
type StorageSet = (key: string, value: string) => Promise<void>;

export interface UnreadEventsStoreDeps {
  getItem: StorageGet;
  setItem: StorageSet;
  /** Defaults to master+category preference check via getItem. */
  isEnabled?: (templateId: string) => Promise<boolean>;
}

export interface UnreadEventsStore {
  list(): Promise<UnreadEvent[]>;
  unreadCount(): Promise<number>;
  ingest(payload: Record<string, unknown>): Promise<IngestResult>;
  markRead(id: string): Promise<boolean>;
  markCategoryRead(category: NotificationPreferenceKey): Promise<number>;
  markAllRead(): Promise<number>;
  refreshFromBills(bills: unknown): Promise<UnreadFeedRefresh>;
  subscribe(listener: (events: UnreadEvent[]) => void): () => void;
}

export function createUnreadEventsStore(
  deps: UnreadEventsStoreDeps,
): UnreadEventsStore {
  const isEnabled =
    deps.isEnabled ??
    ((templateId: string) => isNotificationEnabled(deps.getItem, templateId));

  let chain: Promise<unknown> = Promise.resolve();
  let cached: LedgerState | null = null;
  const listeners = new Set<(events: UnreadEvent[]) => void>();

  function enqueue<T>(fn: () => Promise<T>): Promise<T> {
    const op = chain.catch(() => {}).then(fn);
    chain = op.then(
      () => {},
      () => {},
    );
    return op;
  }

  async function load(): Promise<LedgerState> {
    if (cached) return cached;
    // A failing read rejects instead of caching an empty ledger, so a later
    // retry reads the real persisted state.
    const raw = await deps.getItem(UNREAD_EVENTS_STORAGE_KEY);
    cached = parseUnreadLedger(raw);
    return cached;
  }

  async function persist(state: LedgerState): Promise<void> {
    // Only a durable write updates the cached state; on failure the caller
    // rejects and a retry persists the same mutation again.
    await deps.setItem(UNREAD_EVENTS_STORAGE_KEY, serializeLedger(state));
    cached = state;
  }

  function notify(state: LedgerState): void {
    const snapshot = state.events.map((event) => ({ ...event }));
    listeners.forEach((listener) => {
      try {
        listener(snapshot);
      } catch {}
    });
  }

  function ingestOne(
    state: LedgerState,
    payload: Record<string, unknown>,
  ): Promise<IngestResult> {
    return (async () => {
      const templateId = canonicalTemplateId(payload.template_id);
      if (!templateId) return "invalid";
      const id = stableEventId(payload);
      if (!id) return "invalid";
      if (state.read.includes(id)) return "duplicate";
      if (state.events.some((event) => event.id === id)) return "duplicate";
      if (!(await isEnabled(templateId))) return "disabled";

      const events = [
        ...state.events,
        {
          id,
          templateId,
          title: truncateText(payload.title),
          body: truncateText(payload.body),
          billId: isSafeBillId(payload.bill_id) ? payload.bill_id : null,
        },
      ];
      // Bound the ledger: drop oldest unread events first, but tombstone
      // their IDs so a replay of an evicted event stays deduplicated.
      let read = state.read;
      if (events.length > MAX_UNREAD_EVENTS) {
        const evicted = events.splice(0, events.length - MAX_UNREAD_EVENTS);
        read = withTombstones(
          read,
          evicted.map((event) => event.id),
        );
      }
      const next = { events, read };
      await persist(next);
      notify(next);
      return "added";
    })();
  }

  return {
    list() {
      return enqueue(async () => (await load()).events.map((e) => ({ ...e })));
    },

    unreadCount() {
      return enqueue(async () => (await load()).events.length);
    },

    ingest(payload) {
      return enqueue(async () => ingestOne(await load(), payload));
    },

    markRead(id) {
      return enqueue(async () => {
        if (!isValidEventId(id)) return false;
        const state = await load();
        if (!state.events.some((event) => event.id === id)) return false;
        const read = withTombstones(state.read, [id]);
        const next = {
          events: state.events.filter((event) => event.id !== id),
          read,
        };
        await persist(next);
        notify(next);
        return true;
      });
    },

    markCategoryRead(category) {
      return enqueue(async () => {
        const state = await load();
        const matching = state.events.filter(
          (event) => preferenceKeyForTemplate(event.templateId) === category,
        );
        if (matching.length === 0) return 0;
        const read = withTombstones(
          state.read,
          matching.map((event) => event.id),
        );
        const drop = new Set(matching.map((event) => event.id));
        const next = {
          events: state.events.filter((event) => !drop.has(event.id)),
          read,
        };
        await persist(next);
        notify(next);
        return matching.length;
      });
    },

    markAllRead() {
      return enqueue(async () => {
        const state = await load();
        const marked = state.events.length;
        if (marked === 0) return 0;
        const read = withTombstones(
          state.read,
          state.events.map((event) => event.id),
        );
        const next = { events: [], read };
        await persist(next);
        notify(next);
        return marked;
      });
    },

    refreshFromBills(bills) {
      return enqueue(async () => {
        // An invalid (non-array) feed is a client/transport bug: keep the
        // stored snapshot untouched instead of wiping it.
        if (!Array.isArray(bills)) return { added: 0, seeded: false };

        // A failing snapshot read rejects; nothing is rewritten from guesses.
        const raw = await deps.getItem(UNREAD_FEED_SNAPSHOT_KEY);

        // A missing or malformed snapshot reseeds the baseline so
        // historical bills are not flooded in as new events.
        let seeded = true;
        const previous = new Map<string, string>();
        if (raw !== null) {
          try {
            const parsed: unknown = JSON.parse(raw);
            if (!Array.isArray(parsed)) {
              throw new Error("snapshot is not an array");
            }
            for (const entry of parsed.slice(-MAX_FEED_SNAPSHOT)) {
              if (!Array.isArray(entry) || !isSafeBillId(entry[0]) || typeof entry[1] !== "string") {
                throw new Error("invalid snapshot entry");
              }
              previous.set(entry[0], entry[1]);
            }
            seeded = false;
          } catch {
            previous.clear();
          }
        }

        const candidates: Record<string, unknown>[] = [];
        // Merge into the prior snapshot: a partial feed updates only the
        // bills it contains and never drops the rest.
        const merged = new Map(previous);
        for (const bill of bills) {
          if (!bill || typeof bill !== "object") continue;
          const record = bill as Record<string, unknown>;
          if (!isSafeBillId(record.id)) continue;
          const status =
            typeof record.status === "string"
              ? record.status.toUpperCase()
              : "";
          if (merged.has(record.id)) merged.delete(record.id);
          merged.set(record.id, status);

          if (seeded || previous.get(record.id) === status) continue;
          const feedEvent = FEED_STATUS_EVENTS[status];
          if (!feedEvent) continue;
          candidates.push({
            template_id: feedEvent.templateId,
            bill_id: record.id,
            title: feedEvent.title,
            body: truncateText(record.title_el),
          });
        }

        // Bound the merged snapshot; newest entries win.
        const entries = [...merged.entries()].slice(-MAX_FEED_SNAPSHOT);

        // Ledger ingest first: the snapshot is saved only after every
        // candidate was durably ingested. On a storage failure the refresh
        // rejects and the unchanged snapshot replays the transition on the
        // next run instead of losing it.
        let added = 0;
        for (const candidate of candidates) {
          const result = await ingestOne(await load(), candidate);
          if (result === "added") added += 1;
        }
        await deps.setItem(UNREAD_FEED_SNAPSHOT_KEY, JSON.stringify(entries));
        return { added, seeded };
      });
    },

    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}
