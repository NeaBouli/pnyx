import React, { useEffect, useRef, useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator, ScrollView, Image, Animated } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import { isVerified } from "../lib/crypto-native";
import { fetchAnalyticsOverview } from "../lib/api";
import { isDemoMode } from "../lib/demo";
import { getResult } from "../lib/compassStore";
import { registerForPushNotifications } from "../lib/notifications";
import type { CompassResult } from "../compass/types";
import type { RootStackParams } from "../navigation";
import { colors } from "../theme";
import { Linking, Platform } from "react-native";
import Constants from "expo-constants";

const QUADRANT_COLORS: Record<string, string> = {
  libertarian_left: "#22c55e",
  libertarian_right: "#2563eb",
  authoritarian_left: "#ef4444",
  authoritarian_right: "#f59e0b",
};

type Nav = StackNavigationProp<RootStackParams, "Tabs">;

export default function HomeScreen() {
  const nav = useNavigation<Nav>();
  const [verified, setVerified] = useState<boolean | null>(null);
  const [demo, setDemo] = useState(false);
  const [analytics, setAnalytics] = useState<any>(null);
  const [compassResult, setCompassResult] = useState<CompassResult | null>(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    isVerified().then(setVerified);
    isDemoMode().then(setDemo);
    fetchAnalyticsOverview().then(setAnalytics).catch(() => {});
    getResult().then(setCompassResult);
    isVerified().then((v) => { if (v) registerForPushNotifications().catch(() => {}); });
  }, []);

  // Version check
  const [updateAvailable, setUpdateAvailable] = useState<{version: string; notes: string; url: string; force: boolean} | null>(null);
  useEffect(() => {
    const currentVC = Constants.expoConfig?.android?.versionCode ?? 5;
    fetch("https://api.ekklesia.gr/api/v1/app/version")
      .then(r => r.json())
      .then(data => {
        if (data.latest_version_code > currentVC) {
          setUpdateAvailable({
            version: data.latest_version,
            notes: data.release_notes_el,
            url: data.fdroid_url || data.playstore_url || data.direct_apk_url,
            force: data.force_update || false,
          });
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!compassResult) return;
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 0.6, duration: 1200, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1.0, duration: 1200, useNativeDriver: true }),
      ])
    );
    anim.start();
    return () => anim.stop();
  }, [compassResult]);

  if (verified === null) return <View style={s.center}><ActivityIndicator color={colors.primary} /></View>;

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      {demo && (
        <View style={s.demoBadge}>
          <Text style={s.demoBadgeText}>Demo</Text>
        </View>
      )}
      {updateAvailable && (        <TouchableOpacity          style={{ backgroundColor: "#fef3c7", borderWidth: 1, borderColor: "#f59e0b", borderRadius: 10, padding: 12, marginBottom: 12 }}          onPress={() => Linking.openURL(updateAvailable.url)}        >          <Text style={{ fontWeight: "700", color: "#92400e", fontSize: 13, marginBottom: 4 }}>            {"u26a0ufe0f u039du03adu03b1 u03adu03bau03b4u03bfu03c3u03b7 v" + updateAvailable.version}          </Text>          <Text style={{ color: "#92400e", fontSize: 11 }}>{updateAvailable.notes}</Text>          <Text style={{ color: "#2563eb", fontSize: 12, fontWeight: "700", marginTop: 6 }}>            {"u0395u03bdu03b7u03bcu03adu03c1u03c9u03c3u03b7 u2192"}          </Text>        </TouchableOpacity>      )}
      <View style={s.hero}>
        <Animated.View style={[
          s.compassRing,
          compassResult && {
            borderWidth: 3,
            borderColor: QUADRANT_COLORS[compassResult.quadrant] || "#94a3b8",
            opacity: pulseAnim,
          },
        ]}>
          <Image source={require("../../assets/pnx.png")} style={s.logoImg} resizeMode="contain" />
        </Animated.View>
        <Text style={s.logoText}>εκκλησία</Text>
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

      <Text style={s.disclaimer}>Η εκκλησία δεν είναι κρατική εφαρμογή. Οι ψηφοφορίες έχουν αποκλειστικά ενημερωτικό χαρακτήρα — χωρίς νομική ή πολιτική δεσμευτικότητα.</Text>
      <Text style={s.footer}>εκκλησία · MIT · © 2026 Vendetta Labs</Text>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 40 },
  hero: { alignItems: "center", paddingVertical: 32 },
  compassRing: { width: 136, height: 136, borderRadius: 68, justifyContent: "center", alignItems: "center", marginBottom: 4 },
  logoImg: { width: 120, height: 120 },
  logoText: { fontSize: 32, fontWeight: "900", color: colors.primary, marginBottom: 2 },
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
  disclaimer: { textAlign: "center", fontSize: 10, color: colors.textTertiary, marginBottom: 8, lineHeight: 15, fontStyle: "italic", paddingHorizontal: 10 },
  footer: { textAlign: "center", fontSize: 11, color: colors.textTertiary },
  demoBadge: { position: "absolute", top: 8, right: 8, backgroundColor: "#f97316", borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4, zIndex: 10 },
  demoBadgeText: { color: "#fff", fontSize: 12, fontWeight: "800" },
});
