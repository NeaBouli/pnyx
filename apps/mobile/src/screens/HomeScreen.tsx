import React, { useEffect, useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator, ScrollView, Image } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import { isVerified } from "../lib/crypto-native";
import { fetchAnalyticsOverview } from "../lib/api";
import type { RootStackParams } from "../navigation";
import { colors } from "../theme";

type Nav = StackNavigationProp<RootStackParams, "Tabs">;

export default function HomeScreen() {
  const nav = useNavigation<Nav>();
  const [verified, setVerified] = useState<boolean | null>(null);
  const [analytics, setAnalytics] = useState<any>(null);

  useEffect(() => {
    isVerified().then(setVerified);
    fetchAnalyticsOverview().then(setAnalytics).catch(() => {});
  }, []);

  if (verified === null) return <View style={s.center}><ActivityIndicator color={colors.primary} /></View>;

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      <View style={s.hero}>
        <Image source={require("../../assets/pnx.png")} style={s.logoImg} resizeMode="contain" />
        <Text style={s.sub}>του έθνους</Text>
        <Text style={s.tagline}>Η φωνή σου μετράει.</Text>
      </View>

      <View style={[s.statusCard, verified ? s.statusGreen : s.statusYellow]}>
        <Text style={[s.statusTitle, { color: verified ? colors.success : colors.warning }]}>
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

      {/* Compass + Settings buttons */}
      <View style={s.actionRow}>
        <TouchableOpacity style={s.actionBtn} onPress={() => nav.navigate("Compass" as any)}>
          <Text style={s.actionIcon}>🧭</Text>
          <Text style={s.actionLabel}>Πολιτική Πυξίδα</Text>
        </TouchableOpacity>
        <TouchableOpacity style={s.actionBtn} onPress={() => nav.navigate("Profile" as any)}>
          <Text style={s.actionIcon}>👤</Text>
          <Text style={s.actionLabel}>Προφίλ</Text>
        </TouchableOpacity>
        <TouchableOpacity style={s.actionBtn} onPress={() => nav.navigate("NotificationSettings" as any)}>
          <Text style={s.actionIcon}>⚙️</Text>
          <Text style={s.actionLabel}>Ρυθμίσεις</Text>
        </TouchableOpacity>
      </View>

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
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 40 },
  hero: { alignItems: "center", paddingVertical: 32 },
  logoImg: { width: 120, height: 120, marginBottom: 8 },
  sub: { fontSize: 14, color: colors.textTertiary, letterSpacing: 3, marginTop: -4 },
  tagline: { fontSize: 16, color: colors.textSecondary, marginTop: 8 },
  statusCard: { borderRadius: 12, padding: 14, marginBottom: 16, borderWidth: 1 },
  statusGreen: { backgroundColor: colors.successBg, borderColor: colors.success },
  statusYellow: { backgroundColor: colors.warningBg, borderColor: colors.warning },
  statusTitle: { fontWeight: "800", fontSize: 15 },
  statusSub: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  statsRow: { flexDirection: "row", gap: 8, marginBottom: 16 },
  statCard: { flex: 1, backgroundColor: colors.surface, borderRadius: 12, padding: 12, alignItems: "center", borderWidth: 1, borderColor: colors.border },
  statVal: { fontSize: 20, fontWeight: "900", color: colors.primary },
  statLabel: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  actionRow: { flexDirection: "row", gap: 10, marginBottom: 16 },
  actionBtn: { flex: 1, backgroundColor: colors.surface, borderRadius: 12, padding: 12, alignItems: "center", borderWidth: 1, borderColor: colors.border },
  actionIcon: { fontSize: 22, marginBottom: 4 },
  actionLabel: { fontSize: 10, fontWeight: "700", color: colors.textSecondary },
  btnPrimary: { backgroundColor: colors.primary, borderRadius: 12, padding: 16, alignItems: "center", marginBottom: 16 },
  btnText: { color: "#fff", fontWeight: "800", fontSize: 16 },
  infoBox: { backgroundColor: colors.surface, borderRadius: 12, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: colors.border },
  infoTitle: { fontSize: 15, fontWeight: "800", color: colors.text, marginBottom: 10 },
  infoItem: { fontSize: 13, color: colors.textSecondary, marginBottom: 6 },
  footer: { textAlign: "center", fontSize: 11, color: colors.textTertiary },
});
