import React, { useEffect, useState } from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import { fetchTrending } from "../lib/api";
import type { RootStackParams } from "../navigation";

type Nav = StackNavigationProp<RootStackParams, "Tabs">;

export default function TrendingScreen() {
  const nav = useNavigation<Nav>();
  const [bills, setBills] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTrending(20)
      .then(data => setBills(Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <View style={s.center}><ActivityIndicator color="#2563eb" size="large" /></View>;

  return (
    <FlatList
      data={bills}
      keyExtractor={b => b.id}
      contentContainerStyle={s.list}
      style={{ backgroundColor: "#0f172a" }}
      ListHeaderComponent={
        <View style={s.header}>
          <Text style={s.headerTitle}>Trending Ψηφοφορίες</Text>
          <Text style={s.headerSub}>Κατά relevance score</Text>
        </View>
      }
      ListEmptyComponent={<Text style={s.empty}>Δεν βρέθηκαν trending ψηφοφορίες</Text>}
      renderItem={({ item, index }) => (
        <TouchableOpacity style={s.card} onPress={() => nav.navigate("Vote", { billId: item.id, billTitle: item.title_el })}>
          <View style={s.rank}><Text style={s.rankText}>{index + 1}</Text></View>
          <View style={s.content}>
            <Text style={s.title} numberOfLines={2}>{item.title_el}</Text>
            {item.pill_el && <Text style={s.pill} numberOfLines={1}>{item.pill_el}</Text>}
            <View style={s.footer}>
              <Text style={s.status}>{item.status}</Text>
              {(item.relevance_score ?? 0) > 0 && <Text style={s.score}>▲ {item.relevance_score}</Text>}
            </View>
          </View>
        </TouchableOpacity>
      )}
    />
  );
}

const s = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#0f172a" },
  list: { padding: 12, gap: 8 },
  header: { marginBottom: 12 },
  headerTitle: { fontSize: 20, fontWeight: "900", color: "#e2e8f0" },
  headerSub: { fontSize: 12, color: "#64748b" },
  card: { backgroundColor: "#1e293b", borderRadius: 12, padding: 14, flexDirection: "row", gap: 12 },
  rank: { width: 32, height: 32, borderRadius: 16, backgroundColor: "#2563eb", alignItems: "center", justifyContent: "center" },
  rankText: { color: "#fff", fontWeight: "900", fontSize: 14 },
  content: { flex: 1 },
  title: { fontSize: 14, fontWeight: "700", color: "#e2e8f0", marginBottom: 4 },
  pill: { fontSize: 11, color: "#64748b", marginBottom: 6 },
  footer: { flexDirection: "row", justifyContent: "space-between" },
  status: { fontSize: 11, color: "#94a3b8", fontWeight: "600" },
  score: { fontSize: 11, color: "#22c55e", fontWeight: "700" },
  empty: { color: "#64748b", textAlign: "center", marginTop: 40 },
});
