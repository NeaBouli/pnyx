import React, { useEffect, useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator, ScrollView, Image } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import { isVerified } from "../lib/crypto-native";
import { fetchAnalyticsOverview } from "../lib/api";
import type { RootStackParams } from "../navigation";

type Nav = StackNavigationProp<RootStackParams, "Tabs">;

export default function HomeScreen() {
  const nav = useNavigation<Nav>();
  const [verified, setVerified] = useState<boolean | null>(null);
  const [analytics, setAnalytics] = useState<any>(null);

  useEffect(() => {
    isVerified().then(setVerified);
    fetchAnalyticsOverview().then(setAnalytics).catch(() => {});
  }, []);

  if (verified === null) return <View style={s.center}><ActivityIndicator color="#2563eb" /></View>;

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      <View style={s.hero}>
        <Image source={require("../../assets/pnx.png")} style={s.logoImg} resizeMode="contain" />
        <Text style={s.sub}>του έθνους</Text>
        <Text style={s.tagline}>Η φωνή σου μετράει.</Text>
      </View>

      <View style={[s.statusCard, verified ? s.statusGreen : s.statusYellow]}>
        <Text style={[s.statusTitle, { color: verified ? "#22c55e" : "#f59e0b" }]}>
          {verified ? "✓ Επαληθευμένος" : "Μη επαληθευμένος"}
        </Text>
        <Text style={s.statusSub}>
          {verified ? "Μπορείτε να ψηφίσετε" : "Απαιτείται επαλήθευση"}
        </Text>
      </View>

      {analytics && (
        <View style={s.statsRow}>
          {[
            { label: "Ψήφοι", val: analytics.votes?.total?.toLocaleString() ?? "—" },
            { label: "Ενεργά", val: analytics.bills?.active ?? "—" },
            { label: "Σήμερα", val: analytics.votes?.today ?? "—" },
          ].map(stat => (
            <View key={stat.label} style={s.statCard}>
              <Text style={s.statVal}>{stat.val}</Text>
              <Text style={s.statLabel}>{stat.label}</Text>
            </View>
          ))}
        </View>
      )}

      {!verified && (
        <TouchableOpacity style={s.btnPrimary} onPress={() => nav.navigate("Verify")}>
          <Text style={s.btnText}>Επαλήθευση Ταυτότητας →</Text>
        </TouchableOpacity>
      )}

      <View style={s.infoBox}>
        <Text style={s.infoTitle}>Πώς λειτουργεί;</Text>
        {["🔐 Επαλήθευση μέσω ελληνικής SIM",
          "🗳️ Ψηφίστε σε πραγματικά νομοσχέδια",
          "📊 Δείτε τη διαφορά από τη Βουλή",
          "🔗 Αποτελέσματα στο Arweave",
        ].map(t => <Text key={t} style={s.infoItem}>{t}</Text>)}
      </View>

      <Text style={s.footer}>εκκλησία · MIT · © 2026 Vendetta Labs</Text>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f172a" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#0f172a" },
  content: { padding: 20, paddingBottom: 40 },
  hero: { alignItems: "center", paddingVertical: 32 },
  logoImg: { width: 120, height: 120, marginBottom: 8 },
  sub: { fontSize: 14, color: "#64748b", letterSpacing: 3, marginTop: -4 },
  tagline: { fontSize: 16, color: "#94a3b8", marginTop: 8 },
  statusCard: { borderRadius: 12, padding: 14, marginBottom: 16 },
  statusGreen: { backgroundColor: "#052e16" },
  statusYellow: { backgroundColor: "#431407" },
  statusTitle: { fontWeight: "800", fontSize: 15 },
  statusSub: { fontSize: 12, color: "#94a3b8", marginTop: 2 },
  statsRow: { flexDirection: "row", gap: 8, marginBottom: 16 },
  statCard: { flex: 1, backgroundColor: "#1e293b", borderRadius: 12, padding: 12, alignItems: "center" },
  statVal: { fontSize: 20, fontWeight: "900", color: "#2563eb" },
  statLabel: { fontSize: 11, color: "#64748b", marginTop: 2 },
  btnPrimary: { backgroundColor: "#2563eb", borderRadius: 12, padding: 16, alignItems: "center", marginBottom: 16 },
  btnText: { color: "#fff", fontWeight: "800", fontSize: 16 },
  infoBox: { backgroundColor: "#1e293b", borderRadius: 12, padding: 16, marginBottom: 20 },
  infoTitle: { fontSize: 15, fontWeight: "800", color: "#e2e8f0", marginBottom: 10 },
  infoItem: { fontSize: 13, color: "#94a3b8", marginBottom: 6 },
  footer: { textAlign: "center", fontSize: 11, color: "#334155" },
});
