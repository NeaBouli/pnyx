/**
 * VoteScreen — Ψηφοφορία με βιομετρική πιστοποίηση
 * Biometric Auth → Ed25519 Sign → Submit
 */
import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from "react-native";
import * as LocalAuthentication from "expo-local-authentication";
import type { StackScreenProps } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
import { loadKeypair, loadNullifier, signVote, verifyVote } from "../lib/crypto-native";
import { submitVote } from "../lib/api";
import { colors } from "../theme";

type Props = StackScreenProps<RootStackParams, "Vote">;

const VOTE_OPTIONS = [
  { key: "YES", label: "ΝΑΙ", color: "#2e7d32", icon: "👍" },
  { key: "NO", label: "ΟΧΙ", color: "#c62828", icon: "👎" },
  { key: "ABSTAIN", label: "ΑΠΟΧΗ", color: "#f57f17", icon: "⏸️" },
] as const;

export default function VoteScreen({ route, navigation }: Props) {
  const { billId, billTitle } = route.params;
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  async function handleVote(choice: string) {
    setSelected(choice);

    // Βιομετρική πιστοποίηση
    const biometric = await LocalAuthentication.authenticateAsync({
      promptMessage: "Επιβεβαιώστε την ψήφο σας",
      fallbackLabel: "Χρήση κωδικού",
    });

    if (!biometric.success) {
      setSelected(null);
      Alert.alert("Ακυρώθηκε", "Η βιομετρική πιστοποίηση απέτυχε.");
      return;
    }

    setLoading(true);
    try {
      const keypair = await loadKeypair();
      const nullifier = await loadNullifier();

      if (!keypair || !nullifier) {
        Alert.alert("Σφάλμα", "Δεν βρέθηκε κλειδί. Επαληθεύστε ξανά.");
        navigation.navigate("Verify");
        return;
      }

      // Ed25519: Τοπική υπογραφή με @noble/curves
      const voteParams = { bill_id: billId, vote: choice, nullifier_hash: nullifier };
      const signatureHex = signVote(keypair.privateKeyHex, voteParams);

      // Self-check: Επαλήθευση υπογραφής πριν την υποβολή
      const valid = verifyVote(keypair.publicKeyHex, voteParams, signatureHex);
      if (!valid) {
        Alert.alert("Σφάλμα Κρυπτογραφίας", "Η τοπική επαλήθευση υπογραφής απέτυχε.");
        return;
      }

      const res = await submitVote(nullifier, billId, choice, signatureHex);

      Alert.alert("Επιτυχία ✓", res.message, [
        {
          text: "Αποτελέσματα",
          onPress: () => navigation.replace("Result", { billId, billTitle }),
        },
      ]);
    } catch (err: any) {
      Alert.alert("Σφάλμα", err.message || "Η ψηφοφορία απέτυχε.");
      setSelected(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{billTitle}</Text>
      <Text style={styles.info}>
        Επιλέξτε την ψήφο σας. Απαιτείται βιομετρική πιστοποίηση.
      </Text>

      <View style={styles.options}>
        {VOTE_OPTIONS.map((opt) => (
          <TouchableOpacity
            key={opt.key}
            style={[
              styles.voteButton,
              { borderColor: opt.color },
              selected === opt.key && { backgroundColor: opt.color },
            ]}
            onPress={() => handleVote(opt.key)}
            disabled={loading}
          >
            <Text style={styles.voteIcon}>{opt.icon}</Text>
            <Text
              style={[
                styles.voteLabel,
                selected === opt.key && { color: "#fff" },
              ]}
            >
              {opt.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.loadingText}>Υποβολή ψήφου...</Text>
        </View>
      )}

      <TouchableOpacity
        style={styles.resultsLink}
        onPress={() => navigation.navigate("Result", { billId, billTitle })}
      >
        <Text style={styles.resultsLinkText}>
          Δείτε τα τρέχοντα αποτελέσματα →
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: colors.background },
  title: { fontSize: 20, fontWeight: "bold", color: colors.primary, marginBottom: 8 },
  info: { fontSize: 14, color: colors.textSecondary, marginBottom: 32 },
  options: { gap: 16 },
  voteButton: {
    flexDirection: "row", alignItems: "center", backgroundColor: colors.surface,
    borderWidth: 2, borderRadius: 16, padding: 20, marginBottom: 12,
  },
  voteIcon: { fontSize: 28, marginRight: 16 },
  voteLabel: { fontSize: 20, fontWeight: "bold", color: colors.text },
  loadingOverlay: { alignItems: "center", marginTop: 24 },
  loadingText: { marginTop: 8, color: colors.textSecondary },
  resultsLink: { marginTop: 32, alignItems: "center" },
  resultsLinkText: { color: colors.primary, fontSize: 14 },
});
