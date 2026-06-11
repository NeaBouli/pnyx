import React, { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl, Share, Linking, ScrollView } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import * as SecureStore from "expo-secure-store";
import { fetchBills } from "../lib/api";
import { mergeBillsUnique } from "../lib/bill-feed";
import type { RootStackParams } from "../navigation";
import { colors } from "../theme";

const FORUM_BASE = "https://pnyx.ekklesia.gr/t/";
const PAGE_SIZE = 10;

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

function readableText(value?: string | null) {
  return Boolean(value && value.trim() && !value.includes("[unknown:"));
}

export default function BillsScreen() {
  const nav = useNavigation<Nav>();
  const [bills, setBills] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [hasMore, setHasMore] = useState(true);
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

  const loadPage = useCallback(async (offset: number, reset: boolean) => {
    try {
      const params: {
        periferia_id?: number;
        dimos_id?: number;
        status?: string;
        source?: string;
        governance?: string;
        limit: number;
        offset: number;
      } = { limit: PAGE_SIZE, offset };
      if (userPeriferia) params.periferia_id = userPeriferia;
      if (userDimos) params.dimos_id = userDimos;
      if (["ACTIVE", "ANNOUNCED", "PARLIAMENT_VOTED", "OPEN_END", "WINDOW_24H"].includes(filter)) params.status = filter;
      if (filter === "DIAVGEIA") params.source = "DIAVGEIA";
      if (filter === "PARLIAMENT") params.source = "PARLIAMENT";
      if (["MUNICIPAL", "REGIONAL", "INSTITUTIONAL"].includes(filter)) params.governance = filter;
      let next: any[];
      if (filter === "ALL" && reset && offset === 0) {
        const [allData, parliamentData] = await Promise.all([
          fetchBills({ ...params, limit: PAGE_SIZE * 2 }),
          fetchBills({ ...params, source: "PARLIAMENT", limit: 4, offset: 0 }),
        ]);
        next = mergeBillsUnique(
          Array.isArray(parliamentData) ? parliamentData : [],
          Array.isArray(allData) ? allData : [],
        );
      } else {
        const data = await fetchBills(params);
        next = Array.isArray(data) ? data : [];
      }
      setBills(prev => reset ? next : mergeBillsUnique(prev, next, prev.length + next.length));
      setHasMore(next.length === PAGE_SIZE);
    } catch { /* */ }
    finally { setLoading(false); setRefreshing(false); setLoadingMore(false); }
  }, [filter, userPeriferia, userDimos]);

  const refreshBills = useCallback(() => loadPage(0, true), [loadPage]);
  const loadMoreBills = useCallback(() => {
    setLoadingMore(true);
    loadPage(bills.length, false);
  }, [bills.length, loadPage]);

  useEffect(() => { refreshBills(); }, [refreshBills]);

  // Server filters by region — client only filters by status/source/tab
  const filtered = filter === "ALL" ? bills
    : filter === "ARWEAVE" ? bills.filter(b => b.arweave_tx_id)
    : bills;

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
        {[["ALL", "Όλα"], ["PARLIAMENT", "Βουλή"], ["ACTIVE", "Ενεργά"], ["ANNOUNCED", "Ανακοιν."], ["DIAVGEIA", "Διαύγεια"], ["MUNICIPAL", "Δήμος"], ["REGIONAL", "Περιφ."], ["INSTITUTIONAL", "Φορείς"], ["OPEN_END", "Αρχείο"], ["ARWEAVE", "⛓"]].map(([k, l]) => (
          <TouchableOpacity key={k} onPress={() => setFilter(k)} style={[s.filterBtn, filter === k && s.filterActive]}>
            <Text style={[s.filterTxt, filter === k && s.filterTxtActive]}>{l}</Text>
          </TouchableOpacity>
        ))}
        <TouchableOpacity onPress={() => nav.navigate("Politikoi" as any)} style={[s.filterBtn, { backgroundColor: "#ede9fe", borderColor: "#a855f7" }]}>
          <Text style={[s.filterTxt, { color: "#7c3aed", fontWeight: "800" }]}>Πολιτικοί</Text>
        </TouchableOpacity>
      </ScrollView>
      <FlatList
        style={{ flex: 1 }}
        data={filtered} keyExtractor={b => b.id} contentContainerStyle={[s.list, { paddingBottom: 120 }]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); refreshBills(); }} tintColor={colors.primary} />}
        ListEmptyComponent={<Text style={s.empty}>Δεν βρέθηκαν ψηφοφορίες</Text>}
        ListFooterComponent={hasMore ? (
          <TouchableOpacity
            style={s.moreBtn}
            disabled={loadingMore}
            onPress={loadMoreBills}
          >
            {loadingMore ? (
              <ActivityIndicator color={colors.primary} />
            ) : (
              <Text style={s.moreTxt}>Περισσότερα</Text>
            )}
          </TouchableOpacity>
        ) : null}
        renderItem={({ item }) => (
          <TouchableOpacity style={s.card} onPress={() => {
            nav.navigate("Vote", { billId: item.id, billTitle: item.title_el });
          }} activeOpacity={0.7}>
            <View style={[s.dot, { backgroundColor: STATUS_COLORS[item.status] ?? colors.textTertiary }]} />
            <View style={s.cardContent}>
              <Text style={s.cardTitle}>{item.title_el}</Text>
              {readableText(item.summary_short_el || item.pill_el) && (
                <Text style={s.cardPill} numberOfLines={3}>{item.summary_short_el || item.pill_el}</Text>
              )}
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
                <View style={s.cardActions}>
                  {item.arweave_tx_id != null && (
                    <TouchableOpacity onPress={(e) => { e.stopPropagation(); Linking.openURL(`https://viewblock.io/arweave/tx/${item.arweave_tx_id}`); }} hitSlop={8}>
                      <Text style={{ fontSize: 11, color: "#a855f7", fontWeight: "700" }}>⛓ {item.arweave_tx_id.substring(0, 8)}…</Text>
                    </TouchableOpacity>
                  )}
                  {item.forum_topic_id != null && (
                    <TouchableOpacity onPress={(e) => { e.stopPropagation(); Linking.openURL(`${FORUM_BASE}${item.forum_topic_id}`); }} hitSlop={8}>
                      <Text style={s.actionIcon}>💬</Text>
                    </TouchableOpacity>
                  )}
                  <TouchableOpacity onPress={(e) => { e.stopPropagation(); shareBill(item); }} hitSlop={8}>
                    <Text style={s.actionIcon}>↗</Text>
                  </TouchableOpacity>
                  {VOTABLE.includes(item.status) && item.status !== "OPEN_END" && <Text style={s.actionIcon}>✓</Text>}
                  {item.status === "OPEN_END" && <Text style={[s.actionIcon, { color: "#7c3aed" }]}>⚖</Text>}
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
  cardFooter: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8 },
  cardStatus: { fontSize: 11, fontWeight: "600" },
  cardActions: { flexDirection: "row", gap: 10, alignItems: "center", flexShrink: 0 },
  actionIcon: { fontSize: 16, color: colors.primary, fontWeight: "800" },
  empty: { color: colors.textSecondary, textAlign: "center", marginTop: 40 },
  moreBtn: { marginTop: 8, marginBottom: 24, alignSelf: "center", borderRadius: 999, borderWidth: 1, borderColor: colors.primary, paddingHorizontal: 20, paddingVertical: 10, backgroundColor: colors.surface },
  moreTxt: { color: colors.primary, fontSize: 13, fontWeight: "800" },
});
