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
  Share,
  ScrollView,
} from "react-native";
import * as LocalAuthentication from "expo-local-authentication";
import type { StackScreenProps } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
import { loadKeypair, loadNullifier, signVote, verifyVote } from "../lib/crypto-native";
import { submitVote, correctVote } from "../lib/api";
import { isDemoMode } from "../lib/demo";
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
  const [summary, setSummary] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [billStatus, setBillStatus] = useState<string>("");
  const [hasVoted, setHasVoted] = useState(false);
  const [isCorrected, setIsCorrected] = useState(false);

  React.useEffect(() => {
    const API = process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr";
    fetch(`${API}/api/v1/bills/${encodeURIComponent(billId)}/summary?lang=el`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.summary) setSummary(d.summary); })
      .catch(() => {})
      .finally(() => setSummaryLoading(false));
    // Load bill status
    fetch(`${API}/api/v1/bills/${encodeURIComponent(billId)}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.status) setBillStatus(d.status); })
      .catch(() => {});
  }, [billId]);

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
      // Demo mode: simulate vote without server
      const demo = await isDemoMode();
      if (demo) {
        await new Promise((r) => setTimeout(r, 800));
        Alert.alert(
          "Demo ✓",
          "Demo — ψήφος δεν καταγράφεται",
          [{ text: "Αποτελέσματα", onPress: () => navigation.replace("Result", { billId, billTitle }) }]
        );
        return;
      }

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

  const shareBill = async () => {
    try {
      await Share.share({
        title: billTitle,
        message: `${billTitle}\n\nΨήφισε ανώνυμα στην εκκλησία:\nhttps://ekklesia.gr/el/bills/${billId}`,
      });
    } catch {}
  };

  async function handleCorrection(choice: string) {
    setLoading(true);
    try {
      const keypair = await loadKeypair();
      const nullifier = await loadNullifier();
      if (!keypair || !nullifier) {
        Alert.alert("Σφάλμα", "Δεν βρέθηκε κλειδί.");
        return;
      }
      const voteParams = { bill_id: billId, vote: choice, nullifier_hash: nullifier };
      const signatureHex = signVote(keypair.privateKeyHex, voteParams);
      const res = await correctVote(nullifier, billId, choice, signatureHex);
      setIsCorrected(true);
      Alert.alert("Διόρθωση ✓", "Η ψήφος σας διορθώθηκε επιτυχώς.", [
        { text: "Αποτελέσματα", onPress: () => navigation.replace("Result", { billId, billTitle }) },
      ]);
    } catch (err: any) {
      Alert.alert("Σφάλμα", err.message || "Η διόρθωση απέτυχε.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ paddingBottom: 40 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
        <Text style={[styles.title, { flex: 1 }]}>{billTitle}</Text>
        <TouchableOpacity onPress={shareBill} style={{ padding: 8 }}>
          <Text style={{ fontSize: 20, color: colors.primary }}>↗</Text>
        </TouchableOpacity>
      </View>
      {/* AI Summary */}
      {summaryLoading ? (
        <ActivityIndicator size="small" color={colors.textSecondary} style={{ marginBottom: 16 }} />
      ) : summary ? (
        <View style={{ backgroundColor: "#eff6ff", borderRadius: 12, padding: 14, marginBottom: 16 }}>
          <Text style={{ fontWeight: "700", color: "#1e40af", fontSize: 13, marginBottom: 6 }}>
            Σύνοψη & Ανάλυση
          </Text>
          <Text style={{ color: "#374151", fontSize: 13, lineHeight: 20 }}>{summary}</Text>
        </View>
      ) : null}

      {billStatus === "WINDOW_24H" && (
        <View style={{ backgroundColor: "#fef3c7", borderRadius: 12, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: "#f59e0b" }}>
          <Text style={{ fontWeight: "700", color: "#92400e", fontSize: 13 }}>
            ⚠️ Τελευταίες 24 ώρες — μπορείτε να διορθώσετε την ψήφο σας (μία φορά)
          </Text>
        </View>
      )}
      <Text style={styles.info}>
        {hasVoted && billStatus === "WINDOW_24H" && !isCorrected
          ? "Έχετε ήδη ψηφίσει. Επιλέξτε νέα ψήφο για διόρθωση."
          : "Επιλέξτε την ψήφο σας. Απαιτείται βιομετρική πιστοποίηση."}
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
            onPress={() => hasVoted && billStatus === "WINDOW_24H" && !isCorrected ? handleCorrection(opt.key) : handleVote(opt.key)}
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
    </ScrollView>
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
