/**
 * HomeScreen — Κεντρική Οθόνη
 * Εμφανίζει κατάσταση επαλήθευσης + πλοήγηση
 */
import React, { useCallback, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation";
import { isVerified } from "../lib/crypto-native";

type Props = NativeStackScreenProps<RootStackParamList, "Home">;

export default function HomeScreen({ navigation }: Props) {
  const [verified, setVerified] = useState<boolean | null>(null);

  useFocusEffect(
    useCallback(() => {
      isVerified().then(setVerified);
    }, [])
  );

  if (verified === null) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#1a237e" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.logo}>🏛️</Text>
      <Text style={styles.title}>Εκκλησία.gr</Text>
      <Text style={styles.subtitle}>
        Ψηφιακή Πλατφόρμα Άμεσης Δημοκρατίας
      </Text>

      <View style={styles.statusCard}>
        <Text style={styles.statusLabel}>Κατάσταση:</Text>
        <Text
          style={[
            styles.statusValue,
            { color: verified ? "#2e7d32" : "#c62828" },
          ]}
        >
          {verified ? "✓ Επαληθευμένος" : "✗ Μη επαληθευμένος"}
        </Text>
      </View>

      {!verified && (
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => navigation.navigate("Verify")}
        >
          <Text style={styles.buttonText}>Επαλήθευση Ταυτότητας</Text>
        </TouchableOpacity>
      )}

      <TouchableOpacity
        style={[styles.primaryButton, !verified && styles.disabledButton]}
        disabled={!verified}
        onPress={() => navigation.navigate("Bills")}
      >
        <Text style={styles.buttonText}>Νομοσχέδια & Ψηφοφορία</Text>
      </TouchableOpacity>

      <Text style={styles.disclaimer}>
        Η ψηφοφορία δεν είναι νομικά δεσμευτική. Εκφράζει μόνο τη γνώμη των
        εγγεγραμμένων χρηστών.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: "#f5f5f5", alignItems: "center", justifyContent: "center" },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  logo: { fontSize: 64, marginBottom: 8 },
  title: { fontSize: 28, fontWeight: "bold", color: "#1a237e" },
  subtitle: { fontSize: 14, color: "#666", marginBottom: 32, textAlign: "center" },
  statusCard: {
    flexDirection: "row", alignItems: "center", backgroundColor: "#fff",
    padding: 16, borderRadius: 12, marginBottom: 24, width: "100%",
    shadowColor: "#000", shadowOpacity: 0.1, shadowRadius: 4, elevation: 2,
  },
  statusLabel: { fontSize: 16, color: "#333", marginRight: 8 },
  statusValue: { fontSize: 16, fontWeight: "bold" },
  primaryButton: {
    backgroundColor: "#1a237e", paddingVertical: 14, paddingHorizontal: 32,
    borderRadius: 12, width: "100%", alignItems: "center", marginBottom: 12,
  },
  disabledButton: { backgroundColor: "#999" },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  disclaimer: { fontSize: 11, color: "#999", textAlign: "center", marginTop: 24, paddingHorizontal: 16 },
});
