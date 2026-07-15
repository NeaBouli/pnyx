import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import type { StackScreenProps } from "@react-navigation/stack";
import * as SecureStore from "expo-secure-store";

import type { RootStackParams } from "../navigation";
import {
  fetchConsensusRepresentation,
  type ConsensusRepresentation,
  type ConsensusRepresentationView,
} from "../lib/api";
import {
  CONSENSUS_VIEW_LABELS,
  consensusScoreLabel,
  type ConsensusViewKey,
  unavailableViewMessage,
} from "../lib/consensus-results";
import { colors } from "../theme";

type Props = StackScreenProps<RootStackParams, "DiavgeiaResults">;

function scoreColor(score: number | null): string {
  if (score === null) return colors.textTertiary;
  if (score > 0) return colors.success;
  if (score < 0) return colors.error;
  return colors.warning;
}

export default function DiavgeiaResultsScreen({ navigation }: Props) {
  const [activeView, setActiveView] = useState<ConsensusViewKey>("municipal");
  const [data, setData] = useState<ConsensusRepresentation | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [storedDimos, storedPeriferia] = await Promise.all([
        SecureStore.getItemAsync("user_dimos_id"),
        SecureStore.getItemAsync("user_periferia_id"),
      ]);
      const result = await fetchConsensusRepresentation({
        dimos_id: storedDimos ? Number(storedDimos) : null,
        periferia_id: storedPeriferia ? Number(storedPeriferia) : null,
      });
      setData(result);
      setError("");
      if (!result.views.municipal.available && result.views.regional.available) {
        setActiveView("regional");
      } else if (!result.views.municipal.available && !result.views.regional.available) {
        setActiveView("national");
      }
    } catch {
      setError("Τα συγκεντρωτικά αποτελέσματα δεν είναι διαθέσιμα αυτή τη στιγμή.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  if (loading && !data) {
    return <View style={s.center}><ActivityIndicator size="large" color={colors.primary} /></View>;
  }

  const current: ConsensusRepresentationView | null = data?.views[activeView] ?? null;
  const unavailable = current ? unavailableViewMessage(current) : null;

  return (
    <ScrollView
      style={s.container}
      contentContainerStyle={s.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      <Text style={s.title}>Αποτελέσματα Διαύγειας</Text>
      <Text style={s.subtitle}>
        Συγκεντρωτικές αξιολογήσεις πολιτών, χωρισμένες ανά γεωγραφικό επίπεδο.
      </Text>

      <View style={s.tabs}>
        {(Object.keys(CONSENSUS_VIEW_LABELS) as ConsensusViewKey[]).map((key) => (
          <TouchableOpacity
            key={key}
            style={[s.tab, activeView === key && s.tabActive]}
            onPress={() => setActiveView(key)}
          >
            <Text style={[s.tabText, activeView === key && s.tabTextActive]}>
              {CONSENSUS_VIEW_LABELS[key]}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {error ? <Text style={s.error}>{error}</Text> : null}

      {current && !error ? (
        <>
          {unavailable ? (
            <TouchableOpacity style={s.infoCard} onPress={() => navigation.navigate("Profile")}>
              <Text style={s.infoTitle}>Χρειάζεται γεωγραφική ρύθμιση</Text>
              <Text style={s.infoText}>{unavailable}</Text>
            </TouchableOpacity>
          ) : (
            <>
              <View style={s.summaryCard}>
                <View style={s.metric}>
                  <Text style={s.metricValue}>{current.bill_count}</Text>
                  <Text style={s.metricLabel}>αποφάσεις</Text>
                </View>
                <View style={s.metric}>
                  <Text style={s.metricValue}>{current.consensus_vote_count}</Text>
                  <Text style={s.metricLabel}>αξιολογήσεις</Text>
                </View>
                <View style={s.metric}>
                  <Text style={[s.metricValue, { color: scoreColor(current.weighted_score) }]}>
                    {current.weighted_score === null
                      ? "—"
                      : `${current.weighted_score > 0 ? "+" : ""}${current.weighted_score.toFixed(2)}`}
                  </Text>
                  <Text style={s.metricLabel}>{consensusScoreLabel(current.weighted_score)}</Text>
                </View>
              </View>

              {current.bills.length === 0 ? (
                <View style={s.emptyCard}>
                  <Text style={s.emptyTitle}>Δεν υπάρχουν ακόμη αξιολογήσεις</Text>
                  <Text style={s.infoText}>Η προβολή θα ενημερωθεί μόλις καταγραφούν πραγματικές αξιολογήσεις.</Text>
                </View>
              ) : current.bills.map((bill) => (
                <TouchableOpacity
                  key={bill.bill_id}
                  style={s.billCard}
                  onPress={() => navigation.navigate("Vote", { billId: bill.bill_id, billTitle: bill.title_el })}
                >
                  <View style={s.billHeader}>
                    <Text style={s.billTitle}>{bill.title_el}</Text>
                    <Text style={[s.billScore, { color: scoreColor(bill.consensus_score) }]}>
                      {bill.consensus_score > 0 ? "+" : ""}{bill.consensus_score.toFixed(2)}
                    </Text>
                  </View>
                  {bill.org_label ? <Text style={s.orgLabel}>{bill.org_label}</Text> : null}
                  <Text style={s.voteCount}>{bill.consensus_count} αξιολογήσεις · {consensusScoreLabel(bill.consensus_score)}</Text>
                </TouchableOpacity>
              ))}
            </>
          )}
        </>
      ) : null}

      {data && activeView === "national" && !data.coverage.complete_geographic_representation ? (
        <View style={s.coverageCard}>
          <Text style={s.coverageTitle}>Όρια γεωγραφικής κάλυψης</Text>
          <Text style={s.coverageText}>
            Από τις {data.coverage.total_diavgeia_bills} δημόσιες αποφάσεις της Διαύγειας, {data.coverage.geographically_represented_bills} έχουν ασφαλή γεωγραφική κατηγοριοποίηση. {data.coverage.institutional_or_unresolved_bills} θεσμικές εγγραφές και {data.coverage.geographic_mapping_gaps} γεωγραφικά κενά δεν παρουσιάζονται ως τοπικά αποτελέσματα.
          </Text>
        </View>
      ) : null}

      <View style={s.privacyCard}>
        <Text style={s.privacyTitle}>Ιδιωτικότητα</Text>
        <Text style={s.privacyText}>
          Εμφανίζονται μόνο συγκεντρωτικά σύνολα. Δεν δημοσιεύονται ατομικές ψήφοι, nullifiers ή στοιχεία ταυτότητας. Οι φορείς χωρίς γεωγραφική αντιστοίχιση εξαιρούνται.
        </Text>
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 16, paddingBottom: 48 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background },
  title: { fontSize: 24, fontWeight: "900", color: colors.text },
  subtitle: { fontSize: 13, lineHeight: 19, color: colors.textSecondary, marginTop: 4, marginBottom: 16 },
  tabs: { flexDirection: "row", gap: 6, marginBottom: 16 },
  tab: { flex: 1, minHeight: 48, borderRadius: 8, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 6, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface },
  tabActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  tabText: { fontSize: 11, fontWeight: "800", color: colors.textSecondary, textAlign: "center" },
  tabTextActive: { color: "#fff" },
  error: { color: colors.error, backgroundColor: colors.errorBg, borderRadius: 8, padding: 12, marginBottom: 12 },
  summaryCard: { flexDirection: "row", borderWidth: 1, borderColor: colors.border, borderRadius: 10, backgroundColor: colors.surface, paddingVertical: 14, marginBottom: 14 },
  metric: { flex: 1, alignItems: "center", paddingHorizontal: 4 },
  metricValue: { fontSize: 19, fontWeight: "900", color: colors.text },
  metricLabel: { fontSize: 9, lineHeight: 13, color: colors.textSecondary, textAlign: "center", marginTop: 2 },
  infoCard: { backgroundColor: colors.primaryLight, borderRadius: 10, padding: 16, marginBottom: 14 },
  infoTitle: { color: colors.primary, fontSize: 15, fontWeight: "800", marginBottom: 4 },
  infoText: { color: colors.textSecondary, fontSize: 12, lineHeight: 18 },
  emptyCard: { backgroundColor: colors.surface, borderRadius: 10, borderWidth: 1, borderColor: colors.border, padding: 18, marginBottom: 14 },
  emptyTitle: { color: colors.text, fontSize: 15, fontWeight: "800", marginBottom: 4 },
  billCard: { backgroundColor: colors.surface, borderRadius: 10, borderWidth: 1, borderColor: colors.border, padding: 14, marginBottom: 10 },
  billHeader: { flexDirection: "row", gap: 10, alignItems: "flex-start" },
  billTitle: { flex: 1, color: colors.text, fontSize: 14, fontWeight: "800", lineHeight: 19 },
  billScore: { fontSize: 16, fontWeight: "900" },
  orgLabel: { color: colors.textSecondary, fontSize: 11, marginTop: 6 },
  voteCount: { color: colors.textTertiary, fontSize: 11, marginTop: 8 },
  coverageCard: { backgroundColor: colors.warningBg, borderRadius: 10, borderWidth: 1, borderColor: "#fde68a", padding: 14, marginTop: 8 },
  coverageTitle: { color: "#92400e", fontSize: 13, fontWeight: "800", marginBottom: 4 },
  coverageText: { color: "#a16207", fontSize: 11, lineHeight: 17 },
  privacyCard: { backgroundColor: "#f5f3ff", borderRadius: 10, borderWidth: 1, borderColor: "#ddd6fe", padding: 14, marginTop: 8 },
  privacyTitle: { color: "#6d28d9", fontSize: 13, fontWeight: "800", marginBottom: 4 },
  privacyText: { color: "#5b21b6", fontSize: 11, lineHeight: 17 },
});
