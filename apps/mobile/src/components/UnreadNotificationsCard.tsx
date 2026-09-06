/**
 * UnreadNotificationsCard — GH290 in-app unread counter + event list.
 *
 * Shows the persistent per-event unread state with an explicit per-event
 * "mark read" acknowledgement. Only safe known bill IDs route to the
 * existing Vote/Result screens; system updates stay on the existing
 * in-app update UI. Never opens arbitrary URLs or identity actions.
 */
import React, { useCallback, useEffect, useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import * as SecureStore from "expo-secure-store";
import type { StackNavigationProp } from "@react-navigation/stack";
import {
  getUnreadEventsStore,
  markNotificationEventRead,
} from "../lib/notifications";
import { isSafeBillId, type UnreadEvent } from "../lib/unread-events";
import type { RootStackParams } from "../navigation";
import { colors } from "../theme";

type Nav = StackNavigationProp<RootStackParams, "Tabs">;

const CATEGORY_LABELS: Record<string, string> = {
  vote_open: "🗳️",
  vote_24h: "⏰",
  vote_result: "📊",
  bill_announced: "🏛️",
  weekly_digest: "📋",
  system_update: "⚙️",
};

function routeFor(
  event: UnreadEvent,
): { screen: "Vote" | "Result"; params: { billId: string; billTitle?: string } } | null {
  if (!isSafeBillId(event.billId)) return null;
  const params = { billId: event.billId };
  if (event.templateId === "vote_open" || event.templateId === "vote_24h") return { screen: "Vote", params };
  if (event.templateId === "vote_result") return { screen: "Result", params };
  return null;
}

export function UnreadNotificationsCard() {
  const nav = useNavigation<Nav>();
  const [events, setEvents] = useState<UnreadEvent[]>([]);
  const [language, setLanguage] = useState("el");
  const [error, setError] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const english = language === "en";
  const title = english ? "Notifications" : "Ειδοποιήσεις";
  const readLabel = english ? "Mark read" : "Αναγνώστηκε";
  const openLabel = english ? "Open" : "Άνοιγμα";

  useFocusEffect(useCallback(() => {
    let active = true;
    void SecureStore.getItemAsync("user_language").then((value) => {
      if (active) setLanguage(value === "en" ? "en" : "el");
    }).catch(() => {});
    return () => { active = false; };
  }, []));

  useEffect(() => {
    const store = getUnreadEventsStore();
    let active = true;
    store.list().then((list) => {
      if (active) setEvents(list);
    }).catch(() => { if (active) setError(true); });
    const unsubscribe = store.subscribe((next) => {
      if (active) setEvents(next);
    });
    return () => {
      active = false;
      unsubscribe();
    };
  }, []);

  if (events.length === 0 && !error) return null;

  const open = (event: UnreadEvent) => {
    const route = routeFor(event);
    if (!route) return;
    if (route.screen === "Vote") nav.navigate("Vote", route.params);
    else nav.navigate("Result", route.params);
    void markNotificationEventRead(event.id).catch(() => setError(true));
  };

  const markRead = (event: UnreadEvent) => {
    void markNotificationEventRead(event.id).then(() => setError(false)).catch(() => setError(true));
  };

  return (
    <View
      style={s.card}
      accessibilityLabel={`${title}: ${events.length}`}
    >
      <View style={s.headerRow}>
        <Text style={s.title}>{title}</Text>
        <View style={s.badge}>
          <Text style={s.badgeText}>{events.length > 99 ? "99+" : events.length}</Text>
        </View>
      </View>
      {error ? <Text accessibilityRole="alert" style={s.eventBody}>{english ? "Could not save or load notifications. Please try again." : "Αδυναμία αποθήκευσης ή φόρτωσης ειδοποιήσεων. Δοκιμάστε ξανά."}</Text> : null}
      {[...events].reverse().slice(0, expanded ? events.length : 3).map((event) => {
        const route = routeFor(event);
        return (
          <View key={event.id} style={s.row}>
            <Text style={s.icon}>{CATEGORY_LABELS[event.templateId] ?? "⚙️"}</Text>
            <View style={s.textWrap}>
              <Text style={s.eventTitle} numberOfLines={2}>
                {event.title || event.body}
              </Text>
              {event.title !== event.body && event.body ? (
                <Text style={s.eventBody} numberOfLines={2}>
                  {event.body}
                </Text>
              ) : null}
              <View style={s.actions}>
                {route ? (
                  <TouchableOpacity
                    style={s.openBtn}
                    onPress={() => open(event)}
                    accessibilityRole="button"
                    accessibilityLabel={`${openLabel}: ${event.title || event.body}`}
                  >
                    <Text style={s.openText}>{openLabel}</Text>
                  </TouchableOpacity>
                ) : null}
                <TouchableOpacity
                  style={s.readBtn}
                  onPress={() => markRead(event)}
                  accessibilityRole="button"
                  accessibilityLabel={`${readLabel}: ${event.title || event.body}`}
                >
                  <Text style={s.readText}>{readLabel}</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        );
      })}
      {events.length > 3 ? <TouchableOpacity accessibilityRole="button" accessibilityState={{ expanded }} style={s.readBtn} onPress={() => setExpanded(!expanded)}>
        <Text style={s.readText}>{expanded ? (english ? "Show less" : "Λιγότερα") : (english ? `Show all (${events.length})` : `Όλες (${events.length})`)}</Text>
      </TouchableOpacity> : null}
    </View>
  );
}

const s = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  headerRow: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  title: { flex: 1, fontSize: 15, fontWeight: "800", color: colors.text },
  badge: {
    backgroundColor: colors.primary,
    borderRadius: 12,
    minWidth: 24,
    paddingHorizontal: 7,
    paddingVertical: 2,
    alignItems: "center",
  },
  badgeText: { color: "#fff", fontSize: 12, fontWeight: "800" },
  row: {
    flexDirection: "row",
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  icon: { fontSize: 18, marginRight: 10, width: 26 },
  textWrap: { flex: 1, minWidth: 0 },
  eventTitle: { fontSize: 13, fontWeight: "700", color: colors.text },
  eventBody: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 8 },
  openBtn: {
    backgroundColor: colors.primary,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 12,
    maxWidth: "100%",
  },
  openText: { color: "#fff", fontSize: 12, fontWeight: "700" },
  readBtn: {
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 12,
    maxWidth: "100%",
    borderWidth: 1,
    borderColor: colors.border,
  },
  readText: { color: colors.textSecondary, fontSize: 12, fontWeight: "700" },
});
