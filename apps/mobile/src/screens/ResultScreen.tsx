/**
 * ResultScreen — Αποτελέσματα Ψηφοφορίας
 * Μπάρες + Divergence Score
 */
import React, { useCallback, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import type { StackScreenProps } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
import { fetchResults, type BillResults } from "../lib/api";
import { colors } from "../theme";

type Props = StackScreenProps<RootStackParams, "Result">;

function Bar({ label, count, percent, color }: { label: string; count: number; percent: number; color: string }) {
  return (
    <View style={styles.barRow}>
      <Text style={styles.barLabel}>{label}</Text>
      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width: `${percent}%`, backgroundColor: color }]} />
      </View>
      <Text style={styles.barValue}>{count} ({percent}%)</Text>
    </View>
  );
}

export default function ResultScreen({ route }: Props) {
  const { billId } = route.params;
  const [data, setData] = useState<BillResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetchResults(billId);
      setData(res);
    } catch {
      // silent
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [billId]);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      load();
    }, [load])
  );

  if (loading && !data) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (!data) {
    return (
      <View style={styles.center}>
        <Text style={{ color: colors.textSecondary }}>Δεν βρέθηκαν αποτελέσματα.</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />
      }
    >
      <Text style={styles.title}>{data.title_el}</Text>
      <Text style={styles.totalVotes}>
        Σύνολο ψήφων: {data.total_votes}
      </Text>

      <View style={styles.barsContainer}>
        <Bar label="ΝΑΙ" count={data.yes_count} percent={data.yes_percent} color="#2e7d32" />
        <Bar label="ΟΧΙ" count={data.no_count} percent={data.no_percent} color="#c62828" />
        <Bar label="ΑΠΟΧΗ" count={data.abstain_count} percent={data.abstain_percent} color="#f57f17" />
      </View>

      {data.divergence && (
        <View style={styles.divergenceCard}>
          <Text style={styles.divergenceTitle}>Απόκλιση Πολιτών – Βουλής</Text>
          <Text style={styles.divergenceScore}>
            {(data.divergence.score * 100).toFixed(1)}%
          </Text>
          <Text style={styles.divergenceLabel}>{data.divergence.label_el}</Text>
          <Text style={styles.divergenceHeadline}>
            {data.divergence.headline_el}
          </Text>
          <View style={styles.divergenceRow}>
            <Text style={styles.divergenceDetail}>
              Πολίτες: {data.divergence.citizen_majority}
            </Text>
            {data.divergence.parliament_result && (
              <Text style={styles.divergenceDetail}>
                Βουλή: {data.divergence.parliament_result}
              </Text>
            )}
          </View>
        </View>
      )}

      <Text style={styles.disclaimer}>{data.disclaimer_el}</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: colors.background },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.background },
  title: { fontSize: 20, fontWeight: "bold", color: colors.primary, marginBottom: 4 },
  totalVotes: { fontSize: 14, color: colors.textSecondary, marginBottom: 24 },
  barsContainer: { backgroundColor: colors.surface, borderRadius: 12, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.border },
  barRow: { flexDirection: "row", alignItems: "center", marginBottom: 12 },
  barLabel: { width: 56, fontSize: 13, fontWeight: "bold", color: colors.text },
  barTrack: { flex: 1, height: 20, backgroundColor: colors.surfaceElevated, borderRadius: 10, overflow: "hidden", marginHorizontal: 8 },
  barFill: { height: "100%", borderRadius: 10 },
  barValue: { width: 80, fontSize: 12, color: colors.textSecondary, textAlign: "right" },
  divergenceCard: {
    backgroundColor: colors.warningBg, borderRadius: 12, padding: 16, marginBottom: 16,
    borderLeftWidth: 4, borderLeftColor: colors.warning,
  },
  divergenceTitle: { fontSize: 14, fontWeight: "bold", color: colors.warning, marginBottom: 4 },
  divergenceScore: { fontSize: 32, fontWeight: "bold", color: colors.warning },
  divergenceLabel: { fontSize: 14, color: colors.warning, marginBottom: 8 },
  divergenceHeadline: { fontSize: 13, color: colors.textSecondary, marginBottom: 8, lineHeight: 18 },
  divergenceRow: { flexDirection: "row", justifyContent: "space-between" },
  divergenceDetail: { fontSize: 12, color: colors.textTertiary },
  disclaimer: { fontSize: 11, color: colors.textTertiary, textAlign: "center", marginTop: 8, marginBottom: 32 },
});
