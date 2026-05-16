import React, { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl, Share, Linking } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import { fetchBills } from "../lib/api";
import type { RootStackParams } from "../navigation";
import { colors } from "../theme";

const FORUM_BASE = "https://pnyx.ekklesia.gr/t/";

type Nav = StackNavigationProp<RootStackParams, "Tabs">;

const STATUS_COLORS: Record<string, string> = {
  ACTIVE: colors.success, WINDOW_24H: colors.warning, ANNOUNCED: colors.textTertiary,
  PARLIAMENT_VOTED: colors.primary, OPEN_END: "#a855f7",
};
const STATUS_LABELS: Record<string, string> = {
  ACTIVE: "Ανοιχτή", WINDOW_24H: "24ω", ANNOUNCED: "Ανακοινώθηκε",
  PARLIAMENT_VOTED: "Βουλή", OPEN_END: "Αρχείο",
};
const VOTABLE = ["ACTIVE", "WINDOW_24H", "OPEN_END"];

export default function BillsScreen() {
  const nav = useNavigation<Nav>();
  const [bills, setBills] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState("ALL");

  const load = useCallback(async () => {
    try {
      const data = await fetchBills();
      setBills(Array.isArray(data) ? data : []);
    } catch { /* */ }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = filter === "ALL" ? bills : filter === "ARWEAVE" ? bills.filter(b => b.arweave_tx_id) : bills.filter(b => b.status === filter);

  const shareBill = async (bill: any) => {
    try {
      await Share.share({
        title: bill.title_el,
        message: `${bill.title_el}\n\nΨήφισε ανώνυμα στην εκκλησία:\nhttps://ekklesia.gr/el/bills/${bill.id}`,
      });
    } catch {}
  };

  if (loading) return <View style={s.center}><ActivityIndicator color={colors.primary} size="large" /></View>;

  return (
    <View style={s.container}>
      <View style={s.filterRow}>
        {[["ALL", "Όλα"], ["ACTIVE", "Ενεργά"], ["WINDOW_24H", "24ω"], ["PARLIAMENT_VOTED", "Βουλή"], ["ARWEAVE", "⛓"]].map(([k, l]) => (
          <TouchableOpacity key={k} onPress={() => setFilter(k)} style={[s.filterBtn, filter === k && s.filterActive]}>
            <Text style={[s.filterTxt, filter === k && s.filterTxtActive]}>{l}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <FlatList
        style={{ flex: 1 }}
        data={filtered} keyExtractor={b => b.id} contentContainerStyle={[s.list, { paddingBottom: 120 }]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={colors.primary} />}
        ListEmptyComponent={<Text style={s.empty}>Δεν βρέθηκαν ψηφοφορίες</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={s.card} onPress={() => {
            if (VOTABLE.includes(item.status)) nav.navigate("Vote", { billId: item.id, billTitle: item.title_el });
            else nav.navigate("Result", { billId: item.id });
          }}>
            <View style={[s.dot, { backgroundColor: STATUS_COLORS[item.status] ?? colors.textTertiary }]} />
            <View style={s.cardContent}>
              <Text style={s.cardTitle} numberOfLines={2}>{item.title_el}</Text>
              {item.pill_el && <Text style={s.cardPill} numberOfLines={1}>{item.pill_el}</Text>}
              <View style={s.cardFooter}>
                <Text style={[s.cardStatus, { color: STATUS_COLORS[item.status] ?? colors.textTertiary }]}>{STATUS_LABELS[item.status] ?? item.status}</Text>
                <View style={{ flexDirection: "row", gap: 12, alignItems: "center" }}>
                  {item.arweave_tx_id != null && (
                    <TouchableOpacity onPress={(e) => { e.stopPropagation(); Linking.openURL(`https://arweave.net/${item.arweave_tx_id}`); }} hitSlop={8}>
                      <Text style={{ fontSize: 11, color: "#a855f7", fontWeight: "700" }}>⛓ {item.arweave_tx_id.substring(0, 8)}…</Text>
                    </TouchableOpacity>
                  )}
                  {item.forum_topic_id != null && (
                    <TouchableOpacity onPress={(e) => { e.stopPropagation(); Linking.openURL(`${FORUM_BASE}${item.forum_topic_id}`); }} hitSlop={8}>
                      <Text style={s.forumBtn}>💬</Text>
                    </TouchableOpacity>
                  )}
                  <TouchableOpacity onPress={(e) => { e.stopPropagation(); shareBill(item); }} hitSlop={8}>
                    <Text style={s.shareBtn}>↗</Text>
                  </TouchableOpacity>
                  {VOTABLE.includes(item.status) && <Text style={s.voteHint}>Ψηφίστε →</Text>}
                </View>
              </View>
            </View>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background },
  filterRow: { flexDirection: "row", gap: 6, padding: 12, backgroundColor: colors.surface },
  filterBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20, backgroundColor: colors.surfaceElevated },
  filterActive: { backgroundColor: colors.primary },
  filterTxt: { color: colors.textTertiary, fontSize: 12, fontWeight: "700" },
  filterTxtActive: { color: "#fff" },
  list: { padding: 12, gap: 10 },
  card: { backgroundColor: colors.surface, borderRadius: 12, padding: 14, flexDirection: "row", gap: 10, borderWidth: 1, borderColor: colors.border },
  dot: { width: 10, height: 10, borderRadius: 5, marginTop: 4 },
  cardContent: { flex: 1 },
  cardTitle: { fontSize: 14, fontWeight: "700", color: colors.text, marginBottom: 4 },
  cardPill: { fontSize: 12, color: colors.textSecondary, marginBottom: 6 },
  cardFooter: { flexDirection: "row", justifyContent: "space-between" },
  cardStatus: { fontSize: 11, fontWeight: "600" },
  forumBtn: { fontSize: 14 },
  shareBtn: { fontSize: 16, color: colors.primary, fontWeight: "700" },
  voteHint: { fontSize: 11, color: colors.primary, fontWeight: "700" },
  empty: { color: colors.textSecondary, textAlign: "center", marginTop: 40 },
});
