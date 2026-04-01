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
        <ActivityIndicator size="large" color="#1a237e" />
      </View>
    );
  }

  if (!data) {
    return (
      <View style={styles.center}>
        <Text>Δεν βρέθηκαν αποτελέσματα.</Text>
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
  container: { flex: 1, padding: 24, backgroundColor: "#f5f5f5" },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  title: { fontSize: 20, fontWeight: "bold", color: "#1a237e", marginBottom: 4 },
  totalVotes: { fontSize: 14, color: "#666", marginBottom: 24 },
  barsContainer: { backgroundColor: "#fff", borderRadius: 12, padding: 16, marginBottom: 16 },
  barRow: { flexDirection: "row", alignItems: "center", marginBottom: 12 },
  barLabel: { width: 56, fontSize: 13, fontWeight: "bold", color: "#333" },
  barTrack: { flex: 1, height: 20, backgroundColor: "#e0e0e0", borderRadius: 10, overflow: "hidden", marginHorizontal: 8 },
  barFill: { height: "100%", borderRadius: 10 },
  barValue: { width: 80, fontSize: 12, color: "#555", textAlign: "right" },
  divergenceCard: {
    backgroundColor: "#fff3e0", borderRadius: 12, padding: 16, marginBottom: 16,
    borderLeftWidth: 4, borderLeftColor: "#e65100",
  },
  divergenceTitle: { fontSize: 14, fontWeight: "bold", color: "#e65100", marginBottom: 4 },
  divergenceScore: { fontSize: 32, fontWeight: "bold", color: "#bf360c" },
  divergenceLabel: { fontSize: 14, color: "#e65100", marginBottom: 8 },
  divergenceHeadline: { fontSize: 13, color: "#555", marginBottom: 8, lineHeight: 18 },
  divergenceRow: { flexDirection: "row", justifyContent: "space-between" },
  divergenceDetail: { fontSize: 12, color: "#777" },
  disclaimer: { fontSize: 11, color: "#999", textAlign: "center", marginTop: 8, marginBottom: 32 },
});
