import React, { useEffect, useState } from "react";
import { View, Text, FlatList, StyleSheet, ActivityIndicator, TouchableOpacity } from "react-native";
import { fetchMPRanking } from "../lib/api";
import { colors } from "../theme";

type TabMode = "parties" | "politikoi";

const POLITIKOI_CATEGORIES = [
  { key: "parliament", icon: "🏛️", label: "Βουλευτές", labelEn: "MPs" },
  { key: "periferia", icon: "🗺️", label: "Περιφερειάρχες", labelEn: "Regional Governors" },
  { key: "dimos", icon: "🏘️", label: "Δήμαρχοι", labelEn: "Mayors" },
];

export default function MPScreen() {
  const [mode, setMode] = useState<TabMode>("parties");
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
    <View style={{ flex: 1, backgroundColor: colors.background }}>
      {/* Toggle: Κόμματα ↔ Πολιτικοί */}
      <View style={s.toggle}>
        <TouchableOpacity
          style={[s.toggleBtn, mode === "parties" && s.toggleActive]}
          onPress={() => setMode("parties")}
        >
          <Text style={[s.toggleText, mode === "parties" && s.toggleTextActive]}>📊 Κόμματα</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[s.toggleBtn, mode === "politikoi" && s.toggleActive]}
          onPress={() => setMode("politikoi")}
        >
          <Text style={[s.toggleText, mode === "politikoi" && s.toggleTextActive]}>👤 Πολιτικοί</Text>
        </TouchableOpacity>
      </View>

      {mode === "parties" ? (
        <FlatList
          data={ranking}
          keyExtractor={r => r.party_abbr}
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
      ) : (
        <FlatList
          data={POLITIKOI_CATEGORIES}
          keyExtractor={c => c.key}
          contentContainerStyle={s.list}
          ListHeaderComponent={
            <View style={s.header}>
              <Text style={s.headerTitle}>Πολιτικοί — Αξιολόγηση</Text>
              <Text style={s.headerSub}>Αξιολογήστε εκπροσώπους σε κλίμακα -5 έως +5</Text>
            </View>
          }
          renderItem={({ item }) => (
            <TouchableOpacity style={s.card} activeOpacity={0.7}>
              <Text style={{ fontSize: 32, marginRight: 12 }}>{item.icon}</Text>
              <View style={s.content}>
                <Text style={s.name}>{item.label}</Text>
                <Text style={s.detail}>Αξιολόγηση διαθέσιμη σύντομα</Text>
              </View>
              <Text style={{ color: colors.textTertiary, fontSize: 18 }}>→</Text>
            </TouchableOpacity>
          )}
          ListFooterComponent={
            <View style={{ backgroundColor: colors.primaryLight, borderRadius: 12, padding: 16, marginTop: 12 }}>
              <Text style={{ color: colors.primary, fontWeight: "700", fontSize: 13, marginBottom: 4 }}>
                ℹ️ Πώς λειτουργεί;
              </Text>
              <Text style={{ color: colors.text, fontSize: 12, lineHeight: 18 }}>
                Οι εκπρόσωποι που δέχτηκαν αξιολόγηση μέσω της εφαρμογής εκπρόσωπος
                μπορούν να βαθμολογηθούν σε 8 κατηγορίες. Η αξιολόγηση είναι ανώνυμη,
                liquide (μπορείτε να την αλλάξετε ανά πάσα στιγμή) και διαρκεί όσο
                ο εκπρόσωπος βρίσκεται σε αξίωμα.
              </Text>
            </View>
          }
        />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background },
  toggle: { flexDirection: "row", margin: 12, marginBottom: 0, backgroundColor: colors.surface, borderRadius: 12, borderWidth: 1, borderColor: colors.border, overflow: "hidden" },
  toggleBtn: { flex: 1, paddingVertical: 10, alignItems: "center" },
  toggleActive: { backgroundColor: colors.primary },
  toggleText: { fontSize: 13, fontWeight: "700", color: colors.textSecondary },
  toggleTextActive: { color: "#fff" },
  list: { padding: 12, gap: 8 },
  header: { marginBottom: 12 },
  headerTitle: { fontSize: 20, fontWeight: "900", color: colors.text },
  headerSub: { fontSize: 12, color: colors.textSecondary },
  card: { backgroundColor: colors.surface, borderRadius: 12, padding: 14, flexDirection: "row", alignItems: "center", gap: 10, borderWidth: 1, borderColor: colors.border },
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
