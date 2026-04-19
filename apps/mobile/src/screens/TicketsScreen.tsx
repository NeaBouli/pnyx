import React, { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl, Alert } from "react-native";
import { isVerified } from "../lib/crypto-native";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
import { colors } from "../theme";

type Nav = StackNavigationProp<RootStackParams, "Tabs">;

interface Ticket {
  id: number;
  title: string;
  labels: { name: string; color: string }[];
  reactions: { "+1": number; "-1": number };
  created_at: string;
  state: string;
  html_url: string;
}

const REPO = "NeaBouli/pnyx-community";
const CATEGORY_COLORS: Record<string, string> = {
  bug: colors.error, proposal: colors.primary, vote: colors.success,
  feature: colors.primary, infra: colors.warning, docs: "#8b5cf6",
};
const FILTERS = [
  { key: "all", label: "Όλα" },
  { key: "proposal", label: "Προτάσεις" },
  { key: "bug", label: "Σφάλματα" },
  { key: "vote", label: "Ψηφοφορίες" },
];

function timeAgo(date: string): string {
  const diff = (Date.now() - new Date(date).getTime()) / 1000;
  if (diff < 60) return "τώρα";
  if (diff < 3600) return Math.floor(diff / 60) + "λ";
  if (diff < 86400) return Math.floor(diff / 3600) + "ω";
  return Math.floor(diff / 86400) + "μ";
}

export default function TicketsScreen() {
  const nav = useNavigation<Nav>();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState("all");
  const [verified, setVerified] = useState(false);

  const loadTickets = useCallback(async () => {
    try {
      setError(false);
      const res = await fetch(`https://api.github.com/repos/${REPO}/issues?state=open&per_page=30&sort=created&direction=desc`);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data: Ticket[] = await res.json();
      setTickets(data.filter(t => !t.html_url.includes("/pull/")));
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    isVerified().then(setVerified);
    loadTickets().finally(() => setLoading(false));
  }, [loadTickets]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadTickets();
    setRefreshing(false);
  }, [loadTickets]);

  const filtered = filter === "all" ? tickets : tickets.filter(t => t.labels.some(l => l.name === filter));

  const getCategoryColor = (t: Ticket) => {
    for (const l of t.labels) { if (CATEGORY_COLORS[l.name]) return CATEGORY_COLORS[l.name]; }
    return colors.textTertiary;
  };

  const handleAction = () => {
    if (!verified) {
      Alert.alert(
        "Απαιτείται Επαλήθευση",
        "Για να δημιουργήσετε ticket ή να ψηφίσετε, χρειάζεστε επαλήθευση μέσω smartphone.",
        [
          { text: "Επαλήθευση →", onPress: () => nav.navigate("Verify") },
          { text: "Κλείσιμο", style: "cancel" },
        ]
      );
      return false;
    }
    return true;
  };

  if (loading) return (
    <View style={s.container}>
      <ActivityIndicator color={colors.primary} style={{ marginTop: 60 }} />
      {[1, 2, 3].map(i => <View key={i} style={s.skeleton} />)}
    </View>
  );

  if (error) return (
    <View style={[s.container, s.centerContent]}>
      <Text style={{ fontSize: 40, marginBottom: 12 }}>⚠️</Text>
      <Text style={s.errorText}>Αδυναμία σύνδεσης</Text>
      <TouchableOpacity style={s.retryBtn} onPress={() => { setLoading(true); loadTickets().finally(() => setLoading(false)); }}>
        <Text style={s.retryText}>Δοκιμάστε ξανά</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <View style={s.container}>
      {/* Phase B banner */}
      <View style={s.banner}>
        <Text style={s.bannerText}>📱 Φάση Β — Για tickets/ψήφους χρειάζεστε επαλήθευση smartphone</Text>
      </View>

      {/* Filters */}
      <View style={s.filterRow}>
        {FILTERS.map(f => (
          <TouchableOpacity key={f.key} style={[s.filterBtn, filter === f.key && s.filterActive]} onPress={() => setFilter(f.key)}>
            <Text style={[s.filterText, filter === f.key && s.filterTextActive]}>{f.label}</Text>
          </TouchableOpacity>
        ))}
      </View>
      {/* New ticket button — full width below filters */}
      <TouchableOpacity style={s.newBtnFull} onPress={() => { if (handleAction()) Alert.alert("Σύντομα", "Δημιουργία ticket σύντομα διαθέσιμη"); }}>
        <Text style={s.newBtnText}>+ Νέο Ticket</Text>
      </TouchableOpacity>

      <FlatList
        data={filtered}
        keyExtractor={t => String(t.id)}
        contentContainerStyle={{ padding: 16 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
        renderItem={({ item }) => (
          <View style={[s.card, { borderLeftColor: getCategoryColor(item) }]}>
            <View style={s.cardHeader}>
              {item.labels.slice(0, 2).map(l => (
                <View key={l.name} style={[s.badge, { backgroundColor: (CATEGORY_COLORS[l.name] || colors.textTertiary) + "18" }]}>
                  <Text style={[s.badgeText, { color: CATEGORY_COLORS[l.name] || colors.textTertiary }]}>{l.name}</Text>
                </View>
              ))}
              <Text style={s.cardTime}>{timeAgo(item.created_at)}</Text>
            </View>
            <Text style={s.cardTitle}>{item.title}</Text>
            <View style={s.cardFooter}>
              <TouchableOpacity style={s.voteBtn} onPress={() => { if (handleAction()) Alert.alert("👍", "Vote σύντομα"); }}>
                <Text style={s.voteBtnText}>👍 {item.reactions["+1"]}</Text>
              </TouchableOpacity>
              <Text style={s.cardMeta}>#{item.id}</Text>
            </View>
          </View>
        )}
        ListEmptyComponent={
          <View style={s.centerContent}>
            <Text style={{ fontSize: 40, marginBottom: 12 }}>🎫</Text>
            <Text style={s.emptyTitle}>Δεν υπάρχουν tickets ακόμα</Text>
            <Text style={s.emptySub}>Γίνε ο πρώτος που θα αναφέρει ένα θέμα</Text>
          </View>
        }
      />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  centerContent: { alignItems: "center", justifyContent: "center", paddingTop: 60 },
  banner: { backgroundColor: colors.primaryLight, paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.primary + "30" },
  bannerText: { fontSize: 12, color: colors.primary, fontWeight: "600" },
  filterRow: { flexDirection: "row", gap: 6, paddingHorizontal: 16, paddingVertical: 10, alignItems: "center", backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  filterBtn: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: 16, backgroundColor: colors.surfaceElevated },
  filterActive: { backgroundColor: colors.primary },
  filterText: { fontSize: 12, fontWeight: "700", color: colors.textSecondary },
  filterTextActive: { color: "#fff" },
  newBtnFull: { backgroundColor: colors.primary, marginHorizontal: 16, marginVertical: 8, paddingVertical: 12, borderRadius: 12, alignItems: "center" },
  newBtnText: { color: "#fff", fontSize: 14, fontWeight: "800" },
  card: { backgroundColor: colors.surface, borderRadius: 12, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: colors.border, borderLeftWidth: 4 },
  cardHeader: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 6 },
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  badgeText: { fontSize: 10, fontWeight: "800" },
  cardTime: { marginLeft: "auto", fontSize: 10, color: colors.textTertiary },
  cardTitle: { fontSize: 14, fontWeight: "800", color: colors.text, marginBottom: 8 },
  cardFooter: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  voteBtn: { backgroundColor: colors.surfaceElevated, paddingHorizontal: 12, paddingVertical: 4, borderRadius: 12 },
  voteBtnText: { fontSize: 13, fontWeight: "700", color: colors.text },
  cardMeta: { fontSize: 10, color: colors.textTertiary, fontFamily: "monospace" },
  skeleton: { height: 80, backgroundColor: colors.surfaceElevated, borderRadius: 12, marginHorizontal: 16, marginTop: 12 },
  errorText: { fontSize: 16, fontWeight: "700", color: colors.text, marginBottom: 12 },
  retryBtn: { backgroundColor: colors.primary, paddingHorizontal: 20, paddingVertical: 10, borderRadius: 10 },
  retryText: { color: "#fff", fontWeight: "700" },
  emptyTitle: { fontSize: 16, fontWeight: "800", color: colors.text, marginBottom: 4 },
  emptySub: { fontSize: 13, color: colors.textSecondary },
});
