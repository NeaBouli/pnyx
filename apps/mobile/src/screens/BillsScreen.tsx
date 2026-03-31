/**
 * BillsScreen — Λίστα Νομοσχεδίων
 * Pull-to-refresh + κάρτες + πλοήγηση σε ψηφοφορία
 */
import React, { useCallback, useState } from "react";
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation";
import { fetchBills, type Bill } from "../lib/api";

type Props = NativeStackScreenProps<RootStackParamList, "Bills">;

const STATUS_COLORS: Record<string, string> = {
  ACTIVE: "#2e7d32",
  WINDOW_24H: "#e65100",
  OPEN_END: "#1565c0",
  ANNOUNCED: "#757575",
  PARLIAMENT_VOTED: "#4a148c",
};

export default function BillsScreen({ navigation }: Props) {
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await fetchBills();
      setBills(data);
    } catch {
      // silent
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      load();
    }, [load])
  );

  if (loading && bills.length === 0) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#1a237e" />
      </View>
    );
  }

  return (
    <FlatList
      style={styles.list}
      data={bills}
      keyExtractor={(b) => b.id}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />
      }
      ListEmptyComponent={
        <Text style={styles.empty}>Δεν βρέθηκαν νομοσχέδια.</Text>
      }
      renderItem={({ item }) => (
        <TouchableOpacity
          style={styles.card}
          onPress={() =>
            navigation.navigate("Vote", {
              billId: item.id,
              titleEl: item.title_el,
            })
          }
        >
          <View style={styles.cardHeader}>
            <View
              style={[
                styles.badge,
                { backgroundColor: STATUS_COLORS[item.status] || "#999" },
              ]}
            >
              <Text style={styles.badgeText}>{item.status}</Text>
            </View>
            <Text style={styles.relevance}>▲ {item.relevance_score}</Text>
          </View>
          <Text style={styles.cardTitle}>{item.title_el}</Text>
          <Text style={styles.cardSummary} numberOfLines={2}>
            {item.summary_el}
          </Text>
        </TouchableOpacity>
      )}
    />
  );
}

const styles = StyleSheet.create({
  list: { flex: 1, backgroundColor: "#f5f5f5", padding: 16 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  empty: { textAlign: "center", color: "#999", marginTop: 48, fontSize: 16 },
  card: {
    backgroundColor: "#fff", borderRadius: 12, padding: 16, marginBottom: 12,
    shadowColor: "#000", shadowOpacity: 0.08, shadowRadius: 4, elevation: 2,
  },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  badgeText: { color: "#fff", fontSize: 11, fontWeight: "bold" },
  relevance: { fontSize: 13, color: "#666" },
  cardTitle: { fontSize: 16, fontWeight: "bold", color: "#1a237e", marginBottom: 4 },
  cardSummary: { fontSize: 13, color: "#555", lineHeight: 18 },
});
