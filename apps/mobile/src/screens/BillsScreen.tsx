import React, { useEffect, useState, useCallback, useRef } from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl, Share, Linking, ScrollView } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import { fetchBills } from "../lib/api";
import { mergeBillsUnique, prioritizeBillsPage } from "../lib/bill-feed";
import { availableGeographicFilters, scopedBillQuery } from "../lib/bill-scope";
import { loadUserBillScope } from "../lib/bill-scope-storage";
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

function emptyListMessage(filter: string) {
  if (filter === "ACTIVE") {
    return "Δεν υπάρχουν ανοιχτές ψηφοφορίες αυτή τη στιγμή";
  }
  if (filter === "ANNOUNCED") {
    return "Δεν υπάρχουν νέες ανακοινώσεις αυτή τη στιγμή";
  }
  if (filter === "PARLIAMENT") {
    return "Δεν βρέθηκαν θέματα της Βουλής";
  }
  if (filter === "OPEN_END") {
    return "Δεν υπάρχουν αρχειοθετημένες ψηφοφορίες";
  }
  return "Δεν βρέθηκαν ψηφοφορίες";
}

export default function BillsScreen() {
  const nav = useNavigation<Nav>();
  const [bills, setBills] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [nextOffset, setNextOffset] = useState(0);
  const [filter, setFilter] = useState("ALL");
  const [userPeriferia, setUserPeriferia] = useState<number | null>(null);
  const [userDimos, setUserDimos] = useState<number | null>(null);
  const [hasRegion, setHasRegion] = useState(false);
  const [locationReady, setLocationReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const requestSequence = useRef(0);

  useEffect(() => {
    (async () => {
      const { periferiaId, dimosId } = await loadUserBillScope();

      setUserPeriferia(periferiaId);
      setUserDimos(dimosId);
      setHasRegion(periferiaId !== null);
      setLocationReady(true);
    })();
  }, []);

  const loadPage = useCallback(async (offset: number, reset: boolean) => {
    const requestId = reset ? ++requestSequence.current : requestSequence.current;
    try {
      if (!locationReady) return;
      const scopeParams = scopedBillQuery({ periferiaId: userPeriferia, dimosId: userDimos });
      const params: {
        periferia_id?: number;
        dimos_id?: number;
        status?: string;
        source?: string;
        governance?: string;
        status_any?: string;
        include_institutional?: boolean;
        limit: number;
        offset: number;
      } = { ...scopeParams, limit: PAGE_SIZE, offset };
      if (filter === "ACTIVE") {
        params.status_any = "ACTIVE,WINDOW_24H";
      } else if (["ANNOUNCED", "PARLIAMENT_VOTED", "OPEN_END", "WINDOW_24H"].includes(filter)) {
        params.status = filter;
      }
      if (filter === "DIAVGEIA") params.source = "DIAVGEIA";
      if (filter === "PARLIAMENT") params.source = "PARLIAMENT";
      if (["MUNICIPAL", "REGIONAL"].includes(filter)) params.governance = filter;
      let next: any[];
      let followingOffset: number;
      let moreAvailable: boolean;
      if (filter === "ALL" && reset && offset === 0) {
        const mixedFetchLimit = PAGE_SIZE * 2;
        const [allData, parliamentData] = await Promise.all([
          fetchBills({ ...params, limit: mixedFetchLimit }),
          fetchBills({ ...params, governance: "NATIONAL", source: "PARLIAMENT", limit: 4, offset: 0 }),
        ]);
        const page = prioritizeBillsPage(
          Array.isArray(parliamentData) ? parliamentData : [],
          Array.isArray(allData) ? allData : [],
          PAGE_SIZE,
        );
        next = page.items;
        const allCount = Array.isArray(allData) ? allData.length : 0;
        followingOffset = page.secondaryConsumed;
        moreAvailable = page.secondaryConsumed < allCount || allCount === mixedFetchLimit;
      } else {
        const data = await fetchBills(params);
        next = Array.isArray(data) ? data : [];
        followingOffset = offset + next.length;
        moreAvailable = next.length === PAGE_SIZE;
      }
      if (requestId !== requestSequence.current) return;
      setNextOffset(followingOffset);
      setHasMore(moreAvailable);
      setBills(prev => reset ? next : mergeBillsUnique(prev, next, prev.length + next.length));
      setLoadError(null);
    } catch {
      if (requestId !== requestSequence.current) return;
      setLoadError("Δεν ήταν δυνατή η φόρτωση των ψηφοφοριών. Δοκιμάστε ξανά.");
      if (reset) setBills([]);
    }
    finally {
      if (requestId === requestSequence.current) {
        setLoading(false);
        setRefreshing(false);
        setLoadingMore(false);
      }
    }
  }, [filter, userPeriferia, userDimos, locationReady]);

  const refreshBills = useCallback(() => loadPage(0, true), [loadPage]);
  const loadMoreBills = useCallback(() => {
    if (!hasMore || loadingMore) return;
    setLoadingMore(true);
    loadPage(nextOffset, false);
  }, [hasMore, loadingMore, loadPage, nextOffset]);

  useEffect(() => { if (locationReady) refreshBills(); }, [locationReady, refreshBills]);

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

  if (loading || !locationReady) return <View style={s.center}><ActivityIndicator color={colors.primary} size="large" /></View>;

  const geographicFilters = availableGeographicFilters({ periferiaId: userPeriferia, dimosId: userDimos });
  const filterOptions = [
    ["ALL", "Όλα"], ["PARLIAMENT", "Βουλή"], ["ACTIVE", "Ενεργά"],
    ["ANNOUNCED", "Ανακοιν."], ["DIAVGEIA", "Διαύγεια"],
    ...(geographicFilters.includes("MUNICIPAL") ? [["MUNICIPAL", "Δήμος"]] : []),
    ...(geographicFilters.includes("REGIONAL") ? [["REGIONAL", "Περιφ."]] : []),
    ["OPEN_END", "Αρχείο"], ["ARWEAVE", "⛓"],
  ];

  return (
    <View style={s.container}>
      {!hasRegion && (
        <TouchableOpacity
          style={{ backgroundColor: "#eff6ff", padding: 10, borderBottomWidth: 1, borderBottomColor: "#bfdbfe" }}
          onPress={() => nav.navigate("Profile" as any)}
        >
          <Text style={{ color: "#1e40af", fontSize: 12, textAlign: "center", fontWeight: "600" }}>
            💡 Δηλώστε γεωγραφική περιοχή στο Προφίλ για εξατομικευμένη προβολή
          </Text>
        </TouchableOpacity>
      )}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.filterRow} contentContainerStyle={{ gap: 6, paddingHorizontal: 12, alignItems: "center" }}>
        {filterOptions.map(([k, l]) => (
          <TouchableOpacity key={k} onPress={() => setFilter(k)} style={[s.filterBtn, filter === k && s.filterActive]}>
            <Text style={[s.filterTxt, filter === k && s.filterTxtActive]}>{l}</Text>
          </TouchableOpacity>
        ))}
        <TouchableOpacity onPress={() => nav.navigate("Politikoi" as any)} style={[s.filterBtn, { backgroundColor: "#ede9fe", borderColor: "#a855f7" }]}>
          <Text style={[s.filterTxt, { color: "#7c3aed", fontWeight: "800" }]}>Πολιτικοί</Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => nav.navigate("DiavgeiaResults")}
          style={[s.filterBtn, { backgroundColor: "#ecfdf5", borderColor: "#10b981" }]}
        >
          <Text style={[s.filterTxt, { color: "#047857", fontWeight: "800" }]}>Αποτελέσματα</Text>
        </TouchableOpacity>
      </ScrollView>
      {loadError ? (
        <TouchableOpacity style={s.errorBanner} onPress={refreshBills}>
          <Text style={s.errorText}>{loadError}</Text>
        </TouchableOpacity>
      ) : null}
      <FlatList
        style={{ flex: 1 }}
        data={filtered} keyExtractor={b => b.id} contentContainerStyle={[s.list, { paddingBottom: 120 }]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); refreshBills(); }} tintColor={colors.primary} />}
        ListEmptyComponent={<Text style={s.empty}>{emptyListMessage(filter)}</Text>}
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
  errorBanner: { backgroundColor: colors.errorBg, borderBottomWidth: 1, borderBottomColor: colors.error, padding: 10 },
  errorText: { color: colors.error, textAlign: "center", fontSize: 12, fontWeight: "700" },
});
