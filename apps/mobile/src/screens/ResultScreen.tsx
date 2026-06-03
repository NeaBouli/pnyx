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
  TouchableOpacity,
  Linking,
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

function readableText(value?: string | null) {
  return Boolean(value && value.trim() && !value.includes("[unknown:"));
}

function cleanOfficialText(value?: string | null) {
  if (!readableText(value)) return "";
  const cleaned = String(value)
    .replace(/\[[^\]]*\]\(https?:\/\/[^)]*\)/g, "")
    .replace(/\]\(/g, " ")
    .replace(/[*_`]+/g, "")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\s+/g, " ")
    .trim();
  if (
    cleaned.startsWith("Μετάβαση στο κύριο περιεχόμενο") ||
    cleaned.includes("Ανοίξτε το μενού προσβασιμότητας")
  ) {
    return "";
  }
  return cleaned.slice(0, 1400);
}

function sourceLabel(source?: string | null, sourceKind?: string) {
  if (source === "DIAVGEIA") return "Πηγή — Διαύγεια";
  if (sourceKind === "page") return "Σελίδα Βουλής — συγχρονίζεται το κείμενο";
  return "Πηγή — Βουλή των Ελλήνων";
}

export default function ResultScreen({ route }: Props) {
  const { billId, fromVote } = route.params;
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

  const isHidden = data.results_hidden || (data.status === "ACTIVE" && data.total_votes === 0);
  const summary = readableText(data.summary_short_el) ? data.summary_short_el : readableText(data.pill_el) ? data.pill_el : "";
  const analysis = data.ai_summary_reviewed && readableText(data.summary_long_el) ? data.summary_long_el : "";
  const officialText = !analysis ? cleanOfficialText(data.summary_long_el) : "";
  const sourceUrl = data.official_source_url || (data.source !== "DIAVGEIA" ? data.parliament_url || "" : "");
  const sourceKind = data.official_source_url ? "official" : sourceUrl ? "page" : "none";
  const summaryFallback = sourceUrl
    ? "Το επίσημο κείμενο συγχρονίζεται — διαθέσιμο σύντομα. Δείτε προσωρινά τη σελίδα της πηγής."
    : "Το επίσημο κείμενο συγχρονίζεται — διαθέσιμο σύντομα.";

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />
      }
    >
      <Text style={styles.title}>{data.title_el}</Text>

      <View style={styles.summaryCard}>
        <Text style={styles.summaryTitle}>Σύνοψη</Text>
        <Text style={styles.summaryText}>
          {summary || summaryFallback}
        </Text>
        {analysis ? (
          <>
            <Text style={[styles.summaryTitle, { marginTop: 12 }]}>Ανάλυση</Text>
            <Text style={styles.summaryText}>{analysis}</Text>
          </>
        ) : officialText ? (
          <>
            <Text style={[styles.summaryTitle, { marginTop: 12 }]}>Επίσημο κείμενο</Text>
            <Text style={styles.summaryText}>{officialText}</Text>
            <Text style={styles.sourceNote}>
              Η πλήρης AI ανάλυση δεν έχει ακόμη ελεγχθεί. Εμφανίζεται απόσπασμα από την επίσημη πηγή.
            </Text>
          </>
        ) : null}
      </View>

      {sourceUrl ? (
        <TouchableOpacity
          onPress={() => Linking.openURL(sourceUrl)}
          style={styles.sourceCard}
        >
          <Text style={styles.sourceIcon}>🔗</Text>
          <Text style={styles.sourceText}>{sourceLabel(data.source, sourceKind)}</Text>
          <Text style={styles.sourceArrow}>↗</Text>
        </TouchableOpacity>
      ) : (
        <View style={styles.sourceCard}>
          <Text style={styles.sourceIcon}>ℹ️</Text>
          <Text style={styles.sourceText}>
            Το επίσημο κείμενο συγχρονίζεται — διαθέσιμο σύντομα.
          </Text>
        </View>
      )}

      {isHidden ? (
        <View style={styles.hiddenCard}>
          <Text style={styles.hiddenIcon}>🗳️</Text>
          <Text style={styles.hiddenTitle}>
            {fromVote === true
              ? "Η ψήφος σας καταγράφηκε"
              : "Τα αποτελέσματα δεν είναι ακόμα διαθέσιμα"}
          </Text>
          <Text style={styles.hiddenMessage}>
            Τα αποτελέσματα θα είναι διαθέσιμα μετά την ολοκλήρωση της ψηφοφορίας στη Βουλή
            {data.parliament_vote_date ? ` (${data.parliament_vote_date})` : ""}.
          </Text>
          {fromVote === true && (
            <Text style={styles.hiddenNote}>
              Μπορείτε να αλλάξετε την ψήφο σας μία φορά κατά το 24ωρο παράθυρο πριν την ανακοίνωση των αποτελεσμάτων.
            </Text>
          )}
        </View>
      ) : (
        <>
          <Text style={styles.totalVotes}>
            Σύνολο ψήφων: {data.total_votes}
          </Text>

          <View style={styles.barsContainer}>
            <Bar label="ΝΑΙ" count={data.yes_count} percent={data.yes_percent} color="#2e7d32" />
            <Bar label="ΟΧΙ" count={data.no_count} percent={data.no_percent} color="#c62828" />
            <Bar label="ΑΠΟΧΗ" count={data.abstain_count} percent={data.abstain_percent} color="#f57f17" />
          </View>

          {data.divergence ? (
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
          ) : data.status === "PARLIAMENT_VOTED" ? (
            <View style={styles.pendingCard}>
              <Text style={styles.pendingText}>
                Αποτέλεσμα Βουλής: Αναμονή δεδομένων
              </Text>
              <Text style={styles.pendingSubtext}>
                Η κατανομή ψήφων των κομμάτων θα ενημερωθεί αυτόματα.
              </Text>
            </View>
          ) : null}
        </>
      )}

      <Text style={styles.disclaimer}>{data.disclaimer_el}</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: colors.background },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.background },
  title: { fontSize: 20, fontWeight: "bold", color: colors.primary, marginBottom: 4 },
  summaryCard: { backgroundColor: "#eff6ff", borderRadius: 12, padding: 14, marginTop: 12, marginBottom: 12 },
  summaryTitle: { fontWeight: "700", color: "#1e40af", fontSize: 13, marginBottom: 6 },
  summaryText: { color: "#374151", fontSize: 13, lineHeight: 20 },
  sourceCard: { backgroundColor: "#eff6ff", borderRadius: 10, padding: 12, marginBottom: 12, flexDirection: "row", alignItems: "center" },
  sourceIcon: { fontSize: 14, marginRight: 8 },
  sourceText: { color: "#1d4ed8", fontSize: 13, fontWeight: "600", flex: 1 },
  sourceArrow: { color: "#93c5fd", fontSize: 12 },
  sourceNote: { color: "#64748b", fontSize: 11, lineHeight: 16, marginTop: 8 },
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
  hiddenCard: {
    backgroundColor: colors.surface, borderRadius: 12, padding: 24, marginTop: 16, marginBottom: 16,
    borderWidth: 1, borderColor: colors.primary, alignItems: "center",
  },
  hiddenIcon: { fontSize: 48, marginBottom: 12 },
  hiddenTitle: { fontSize: 18, fontWeight: "bold", color: colors.primary, marginBottom: 8, textAlign: "center" },
  hiddenMessage: { fontSize: 14, color: colors.text, textAlign: "center", lineHeight: 20, marginBottom: 12 },
  hiddenNote: { fontSize: 12, color: colors.textSecondary, textAlign: "center", lineHeight: 18, fontStyle: "italic" },
  pendingCard: {
    backgroundColor: "#fef3c7", borderRadius: 12, padding: 16, marginBottom: 16,
    borderLeftWidth: 4, borderLeftColor: "#f59e0b", alignItems: "center",
  },
  pendingText: { fontSize: 14, fontWeight: "bold", color: "#92400e", marginBottom: 4 },
  pendingSubtext: { fontSize: 12, color: "#a16207", textAlign: "center" },
});
