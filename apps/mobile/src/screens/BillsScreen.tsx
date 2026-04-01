import React, { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import { fetchBills } from "../lib/api";
import type { RootStackParams } from "../navigation";

type Nav = StackNavigationProp<RootStackParams, "Tabs">;

const STATUS_COLORS: Record<string, string> = {
  ACTIVE: "#22c55e", WINDOW_24H: "#f59e0b", ANNOUNCED: "#94a3b8",
  PARLIAMENT_VOTED: "#2563eb", OPEN_END: "#a855f7",
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

  const filtered = filter === "ALL" ? bills : bills.filter(b => b.status === filter);

  if (loading) return <View style={s.center}><ActivityIndicator color="#2563eb" size="large" /></View>;

  return (
    <View style={s.container}>
      <View style={s.filterRow}>
        {[["ALL", "Όλα"], ["ACTIVE", "Ενεργά"], ["WINDOW_24H", "24ω"], ["PARLIAMENT_VOTED", "Βουλή"]].map(([k, l]) => (
          <TouchableOpacity key={k} onPress={() => setFilter(k)} style={[s.filterBtn, filter === k && s.filterActive]}>
            <Text style={[s.filterTxt, filter === k && s.filterTxtActive]}>{l}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <FlatList
        data={filtered} keyExtractor={b => b.id} contentContainerStyle={s.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor="#2563eb" />}
        ListEmptyComponent={<Text style={s.empty}>Δεν βρέθηκαν ψηφοφορίες</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={s.card} onPress={() => {
            if (VOTABLE.includes(item.status)) nav.navigate("Vote", { billId: item.id, billTitle: item.title_el });
            else nav.navigate("Result", { billId: item.id });
          }}>
            <View style={[s.dot, { backgroundColor: STATUS_COLORS[item.status] ?? "#94a3b8" }]} />
            <View style={s.cardContent}>
              <Text style={s.cardTitle} numberOfLines={2}>{item.title_el}</Text>
              {item.pill_el && <Text style={s.cardPill} numberOfLines={1}>{item.pill_el}</Text>}
              <View style={s.cardFooter}>
                <Text style={[s.cardStatus, { color: STATUS_COLORS[item.status] ?? "#94a3b8" }]}>{STATUS_LABELS[item.status] ?? item.status}</Text>
                {VOTABLE.includes(item.status) && <Text style={s.voteHint}>Ψηφίστε →</Text>}
              </View>
            </View>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f172a" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#0f172a" },
  filterRow: { flexDirection: "row", gap: 6, padding: 12, backgroundColor: "#1e293b" },
  filterBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20, backgroundColor: "#334155" },
  filterActive: { backgroundColor: "#2563eb" },
  filterTxt: { color: "#94a3b8", fontSize: 12, fontWeight: "700" },
  filterTxtActive: { color: "#fff" },
  list: { padding: 12, gap: 10 },
  card: { backgroundColor: "#1e293b", borderRadius: 12, padding: 14, flexDirection: "row", gap: 10 },
  dot: { width: 10, height: 10, borderRadius: 5, marginTop: 4 },
  cardContent: { flex: 1 },
  cardTitle: { fontSize: 14, fontWeight: "700", color: "#e2e8f0", marginBottom: 4 },
  cardPill: { fontSize: 12, color: "#64748b", marginBottom: 6 },
  cardFooter: { flexDirection: "row", justifyContent: "space-between" },
  cardStatus: { fontSize: 11, fontWeight: "600" },
  voteHint: { fontSize: 11, color: "#2563eb", fontWeight: "700" },
  empty: { color: "#64748b", textAlign: "center", marginTop: 40 },
});
