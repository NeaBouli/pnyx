import React, { useEffect, useState } from "react";
import { View, Text, FlatList, StyleSheet, ActivityIndicator } from "react-native";
import { fetchMPRanking } from "../lib/api";
import { colors } from "../theme";

export default function MPScreen() {
  const [ranking, setRanking] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMPRanking()
      .then(data => setRanking(data.ranking || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <View style={s.center}><ActivityIndicator color={colors.primary} size="large" /></View>;

  return (
    <FlatList
      data={ranking}
      keyExtractor={r => r.party_abbr}
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={s.list}
      ListHeaderComponent={
        <View style={s.header}>
          <Text style={s.headerTitle}>Κόμματα vs Πολίτες</Text>
          <Text style={s.headerSub}>Ποιο κόμμα ψηφίζει όπως η πλειοψηφία;</Text>
        </View>
      }
      ListEmptyComponent={<Text style={s.empty}>Δεν υπάρχουν αρκετά δεδομένα.</Text>}
      renderItem={({ item }) => (
        <View style={s.card}>
          <View style={[s.colorBar, { backgroundColor: item.color_hex || colors.primary }]} />
          <View style={s.content}>
            <View style={s.row}>
              <Text style={s.rank}>#{item.rank}</Text>
              <Text style={s.name}>{item.party_name_el}</Text>
              <Text style={[s.pct, { color: item.color_hex || colors.primary }]}>{item.agreement_pct}%</Text>
            </View>
            <View style={s.barWrap}>
              <View style={[s.bar, { width: `${item.agreement_pct}%`, backgroundColor: item.color_hex || colors.primary }]} />
            </View>
            <Text style={s.detail}>{item.bills_agree} σύγκλιση · {item.bills_analyzed - item.bills_agree} απόκλιση</Text>
          </View>
        </View>
      )}
    />
  );
}

const s = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background },
  list: { padding: 12, gap: 8 },
  header: { marginBottom: 12 },
  headerTitle: { fontSize: 20, fontWeight: "900", color: colors.text },
  headerSub: { fontSize: 12, color: colors.textSecondary },
  card: { backgroundColor: colors.surface, borderRadius: 12, padding: 14, flexDirection: "row", gap: 10, borderWidth: 1, borderColor: colors.border },
  colorBar: { width: 4, borderRadius: 2, alignSelf: "stretch" },
  content: { flex: 1 },
  row: { flexDirection: "row", alignItems: "center", marginBottom: 8, gap: 8 },
  rank: { fontSize: 12, color: colors.textSecondary, fontWeight: "700", width: 24 },
  name: { flex: 1, fontSize: 14, fontWeight: "700", color: colors.text },
  pct: { fontSize: 20, fontWeight: "900" },
  barWrap: { height: 6, backgroundColor: colors.surfaceElevated, borderRadius: 3, overflow: "hidden", marginBottom: 6 },
  bar: { height: "100%", borderRadius: 3 },
  detail: { fontSize: 11, color: colors.textSecondary },
  empty: { color: colors.textSecondary, textAlign: "center", marginTop: 40 },
});
