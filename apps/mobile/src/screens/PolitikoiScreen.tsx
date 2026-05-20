/**
 * PolitikoiScreen — Λίστα αξιολογούμενων πολιτικών
 * NEA-189: Politician Evaluation
 */
import React, { useEffect, useState, useCallback } from "react";
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  ActivityIndicator, RefreshControl,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import { fetchPoliticians } from "../lib/api";
import type { Politician } from "../lib/api";
import type { RootStackParams } from "../navigation";
import { colors } from "../theme";

type Nav = StackNavigationProp<RootStackParams, "Politikoi">;

const ROLE_LABELS: Record<string, string> = {
  "Βουλευτής": "Βουλευτής",
  "Περιφερειάρχης": "Περιφερειάρχης",
  "Δήμαρχος": "Δήμαρχος",
  "Δημοτικός Σύμβουλος": "Δημ. Σύμβουλος",
};

const ROLE_ICONS: Record<string, string> = {
  "Βουλευτής": "🏛️",
  "Περιφερειάρχης": "🗺️",
  "Δήμαρχος": "🏙️",
  "Δημοτικός Σύμβουλος": "📋",
};

function ScoreBar({ score }: { score: number | null }) {
  if (score === null) return <Text style={styles.noScore}>Χωρίς αξιολόγηση</Text>;
  const normalized = ((score + 5) / 10) * 100;
  const color = score >= 2 ? colors.success : score >= 0 ? colors.warning : colors.error;
  return (
    <View style={styles.scoreRow}>
      <View style={styles.barBg}>
        <View style={[styles.barFill, { width: `${normalized}%`, backgroundColor: color }]} />
      </View>
      <Text style={[styles.scoreText, { color }]}>
        {score > 0 ? "+" : ""}{score.toFixed(1)}
      </Text>
    </View>
  );
}

export default function PolitikoiScreen() {
  const nav = useNavigation<Nav>();
  const [politicians, setPoliticians] = useState<Politician[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await fetchPoliticians();
      setPoliticians(Array.isArray(data) ? data : []);
    } catch { /* */ }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return <View style={styles.center}><ActivityIndicator size="large" color={colors.primary} /></View>;
  }

  return (
    <View style={styles.container}>
      {politicians.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyIcon}>🏛️</Text>
          <Text style={styles.emptyText}>Δεν υπάρχουν αξιολογούμενοι εκπρόσωποι ακόμα.</Text>
        </View>
      ) : (
        <FlatList
          data={politicians}
          keyExtractor={(item) => item.ada_number}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
          contentContainerStyle={{ padding: 16 }}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.card}
              activeOpacity={0.7}
              onPress={() => nav.navigate("EvaluatePolitician", { adaNumber: item.ada_number, orgLabel: item.org_label })}
            >
              <View style={styles.cardHeader}>
                <Text style={styles.roleIcon}>{ROLE_ICONS[item.role] || "👤"}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.orgLabel} numberOfLines={2}>{item.org_label || item.ada_number}</Text>
                  <Text style={styles.roleBadge}>{ROLE_LABELS[item.role] || item.role}{item.region ? ` · ${item.region}` : ""}</Text>
                </View>
              </View>
              <ScoreBar score={item.avg_score} />
              <Text style={styles.evalCount}>
                {item.evaluator_count} {item.evaluator_count === 1 ? "πολίτης" : "πολίτες"}
              </Text>
            </TouchableOpacity>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 32 },
  emptyIcon: { fontSize: 48, marginBottom: 12 },
  emptyText: { fontSize: 15, color: colors.textSecondary, textAlign: "center" },
  card: {
    backgroundColor: colors.surface, borderRadius: 12, padding: 16,
    marginBottom: 12, borderWidth: 1, borderColor: colors.border,
    shadowColor: colors.cardShadow, shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1, shadowRadius: 4, elevation: 2,
  },
  cardHeader: { flexDirection: "row", alignItems: "center", marginBottom: 10 },
  roleIcon: { fontSize: 28, marginRight: 12 },
  orgLabel: { fontSize: 15, fontWeight: "800", color: colors.text },
  roleBadge: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  scoreRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  barBg: { flex: 1, height: 8, backgroundColor: colors.surfaceElevated, borderRadius: 4, overflow: "hidden" },
  barFill: { height: 8, borderRadius: 4 },
  scoreText: { fontSize: 16, fontWeight: "900", width: 45, textAlign: "right" },
  noScore: { fontSize: 12, color: colors.textTertiary, fontStyle: "italic" },
  evalCount: { fontSize: 11, color: colors.textTertiary, marginTop: 6, textAlign: "right" },
});
