import React, { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl, Share, Linking, ScrollView } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import * as SecureStore from "expo-secure-store";
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
  const [userPeriferia, setUserPeriferia] = useState<number | null>(null);
  const [userDimos, setUserDimos] = useState<number | null>(null);
  const [hasRegion, setHasRegion] = useState(false);

  useEffect(() => {
    (async () => {
      const p = await SecureStore.getItemAsync("user_periferia_id");
      const d = await SecureStore.getItemAsync("user_dimos_id");
      if (p) { setUserPeriferia(Number(p)); setHasRegion(true); }
      if (d) setUserDimos(Number(d));
    })();
  }, []);

  const load = useCallback(async () => {
    try {
      const data = await fetchBills();
      setBills(Array.isArray(data) ? data : []);
    } catch { /* */ }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = filter === "ALL" ? bills
    : filter === "ARWEAVE" ? bills.filter(b => b.arweave_tx_id)
    : filter === "DIAVGEIA" ? bills.filter(b => b.source === "DIAVGEIA")
    : filter === "MUNICIPAL" ? bills.filter(b => b.governance_level === "MUNICIPAL")
    : filter === "REGIONAL" ? bills.filter(b => b.governance_level === "REGIONAL")
    : filter === "INSTITUTIONAL" ? bills.filter(b => b.governance_level === "INSTITUTIONAL")
    : filter === "OPEN_END" ? bills.filter(b => b.status === "OPEN_END")
    : bills.filter(b => b.status === filter);

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
      {!hasRegion && (
        <TouchableOpacity
          style={{ backgroundColor: "#eff6ff", padding: 10, borderBottomWidth: 1, borderBottomColor: "#bfdbfe" }}
          onPress={() => nav.navigate("Profile" as any)}
        >
          <Text style={{ color: "#1e40af", fontSize: 12, textAlign: "center", fontWeight: "600" }}>
            💡 Ορίστε εκλογική περιφέρεια στο Προφίλ για εξατομικευμένη προβολή
          </Text>
        </TouchableOpacity>
      )}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.filterRow} contentContainerStyle={{ gap: 6, paddingHorizontal: 12, alignItems: "center" }}>
        {[["ALL", "Όλα"], ["ACTIVE", "Ενεργά"], ["DIAVGEIA", "Διαύγεια"], ["MUNICIPAL", "Δήμος"], ["REGIONAL", "Περιφ."], ["INSTITUTIONAL", "Φορείς"], ["PARLIAMENT_VOTED", "Βουλή"], ["OPEN_END", "Αρχείο"], ["ARWEAVE", "⛓"]].map(([k, l]) => (
          <TouchableOpacity key={k} onPress={() => setFilter(k)} style={[s.filterBtn, filter === k && s.filterActive]}>
            <Text style={[s.filterTxt, filter === k && s.filterTxtActive]}>{l}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      <FlatList
        style={{ flex: 1 }}
        data={filtered} keyExtractor={b => b.id} contentContainerStyle={[s.list, { paddingBottom: 120 }]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={colors.primary} />}
        ListEmptyComponent={<Text style={s.empty}>Δεν βρέθηκαν ψηφοφορίες</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={s.card} onPress={() => {
            if (item.status === "PARLIAMENT_VOTED")
              nav.navigate("Result", { billId: item.id, billTitle: item.title_el });
            else
              nav.navigate("Vote", { billId: item.id, billTitle: item.title_el });
          }}>
            <View style={[s.dot, { backgroundColor: STATUS_COLORS[item.status] ?? colors.textTertiary }]} />
            <View style={s.cardContent}>
              <Text style={s.cardTitle} numberOfLines={2}>{item.title_el}</Text>
              {item.pill_el && <Text style={s.cardPill} numberOfLines={1}>{item.pill_el}</Text>}
              <View style={s.cardFooter}>
                <View style={{ flexDirection: "row", gap: 6, alignItems: "center" }}>
                  <Text style={[s.cardStatus, { color: STATUS_COLORS[item.status] ?? colors.textTertiary }]}>{STATUS_LABELS[item.status] ?? item.status}</Text>
                  {item.source === "DIAVGEIA" && (
                    <Text style={{ fontSize: 9, fontWeight: "800", color: "#0369a1", backgroundColor: "#e0f2fe", paddingHorizontal: 4, paddingVertical: 1, borderRadius: 4, overflow: "hidden" }}>ΔΙΑΥΓΕΙΑ</Text>
                  )}
                  {item.status === "OPEN_END" && item.consensus_count > 0 && (
                    <Text style={{ fontSize: 10, fontWeight: "700", color: (item.consensus_score || 0) >= 0 ? "#22c55e" : "#ef4444" }}>
                      ⚖️ {(item.consensus_score || 0) > 0 ? "+" : ""}{(item.consensus_score || 0).toFixed(1)}
                    </Text>
                  )}
                </View>
                <View style={{ flexDirection: "row", gap: 12, alignItems: "center" }}>
                  {item.arweave_tx_id != null && (
                    <TouchableOpacity onPress={(e) => { e.stopPropagation(); Linking.openURL(`https://viewblock.io/arweave/tx/${item.arweave_tx_id}`); }} hitSlop={8}>
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
                  {item.status === "OPEN_END" && <Text style={[s.voteHint, { color: "#7c3aed" }]}>Αξιολόγηση →</Text>}
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
  filterRow: { flexGrow: 0, height: 48, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
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
