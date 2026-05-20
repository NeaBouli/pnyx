/**
 * EvaluatePoliticianScreen — 8 Fragen -5 bis +5
 * NEA-189: Politician Evaluation
 */
import React, { useEffect, useState } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Alert,
} from "react-native";
import * as LocalAuthentication from "expo-local-authentication";
import type { StackScreenProps } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
import { fetchPoliticianQuestions, fetchPoliticianScores, submitEvaluation } from "../lib/api";
import type { EvalQuestion, EvalScores } from "../lib/api";
import { loadKeypair, loadNullifier, signEvaluation } from "../lib/crypto-native";
import { isDemoMode } from "../lib/demo";
import { colors } from "../theme";

type Props = StackScreenProps<RootStackParams, "EvaluatePolitician">;

const SCORE_LABELS = [
  { val: -5, label: "-5" }, { val: -3, label: "-3" }, { val: -1, label: "-1" },
  { val: 0, label: "0" },
  { val: 1, label: "+1" }, { val: 3, label: "+3" }, { val: 5, label: "+5" },
];

function ScoreSelector({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <View style={styles.selectorRow}>
      {SCORE_LABELS.map(({ val, label }) => (
        <TouchableOpacity
          key={val}
          style={[
            styles.scoreBtn,
            value === val && styles.scoreBtnActive,
            val < 0 && value === val && { backgroundColor: colors.error },
            val === 0 && value === val && { backgroundColor: colors.warning },
            val > 0 && value === val && { backgroundColor: colors.success },
          ]}
          onPress={() => onChange(val)}
        >
          <Text style={[styles.scoreBtnText, value === val && styles.scoreBtnTextActive]}>
            {label}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

export default function EvaluatePoliticianScreen({ route, navigation }: Props) {
  const { adaNumber, orgLabel } = route.params;
  const [questions, setQuestions] = useState<EvalQuestion[]>([]);
  const [scores, setScores] = useState<Record<number, number>>({});
  const [existingScores, setExistingScores] = useState<EvalScores | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [qs, sc] = await Promise.all([
          fetchPoliticianQuestions(adaNumber),
          fetchPoliticianScores(adaNumber),
        ]);
        setQuestions(qs);
        setExistingScores(sc);
        // Init all scores to 0
        const init: Record<number, number> = {};
        qs.forEach(q => { init[q.id] = 0; });
        setScores(init);
      } catch { /* */ }
      finally { setLoading(false); }
    })();
  }, [adaNumber]);

  async function handleSubmit() {
    const demo = await isDemoMode();
    if (demo) {
      Alert.alert("Demo", "Στο demo mode δεν μπορείτε να αξιολογήσετε.");
      return;
    }

    // Biometric auth
    const bio = await LocalAuthentication.authenticateAsync({
      promptMessage: "Επιβεβαιώστε την αξιολόγηση",
      fallbackLabel: "Χρήση κωδικού",
    });
    if (!bio.success) {
      Alert.alert("Ακυρώθηκε", "Η βιομετρική πιστοποίηση απέτυχε.");
      return;
    }

    setSubmitting(true);
    try {
      const keypair = await loadKeypair();
      const nullifier = await loadNullifier();
      if (!keypair || !nullifier) {
        Alert.alert("Σφάλμα", "Δεν βρέθηκε κλειδί. Επαληθεύστε πρώτα την ταυτότητά σας.");
        return;
      }

      const signatureHex = signEvaluation(keypair.privateKeyHex, adaNumber, nullifier);
      const scoreList = Object.entries(scores).map(([qid, score]) => ({
        question_id: Number(qid),
        score,
      }));

      await submitEvaluation(adaNumber, nullifier, scoreList, signatureHex);
      setSubmitted(true);

      // Reload scores
      const sc = await fetchPoliticianScores(adaNumber);
      setExistingScores(sc);
    } catch (e: any) {
      Alert.alert("Σφάλμα", e.message || "Αποτυχία αποστολής αξιολόγησης.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <View style={styles.center}><ActivityIndicator size="large" color={colors.primary} /></View>;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
      <Text style={styles.orgLabel}>{orgLabel}</Text>

      {/* Existing scores */}
      {existingScores && existingScores.total_evaluations > 0 && (
        <View style={styles.existingCard}>
          <Text style={styles.existingTitle}>
            Τρέχουσα αξιολόγηση: {existingScores.total_avg !== null ? (existingScores.total_avg > 0 ? "+" : "") + existingScores.total_avg : "—"}
          </Text>
          <Text style={styles.existingCount}>
            {existingScores.total_evaluations} αξιολογήσεις από πολίτες
          </Text>
        </View>
      )}

      {submitted ? (
        <View style={styles.successCard}>
          <Text style={styles.successIcon}>✓</Text>
          <Text style={styles.successText}>Η αξιολόγησή σας καταχωρήθηκε!</Text>
          <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
            <Text style={styles.backBtnText}>← Πίσω</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <>
          <Text style={styles.instructions}>
            Αξιολογήστε τον εκπρόσωπο σε κάθε κατηγορία (-5 έως +5):
          </Text>

          {questions.map((q) => (
            <View key={q.id} style={styles.questionCard}>
              <Text style={styles.category}>{q.category?.toUpperCase()}</Text>
              <Text style={styles.questionText}>{q.question_el}</Text>
              <ScoreSelector value={scores[q.id] ?? 0} onChange={(v) => setScores(prev => ({ ...prev, [q.id]: v }))} />
            </View>
          ))}

          <TouchableOpacity
            style={[styles.submitBtn, submitting && { opacity: 0.6 }]}
            onPress={handleSubmit}
            disabled={submitting}
          >
            {submitting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.submitBtnText}>Υποβολή Αξιολόγησης</Text>
            )}
          </TouchableOpacity>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  orgLabel: { fontSize: 20, fontWeight: "900", color: colors.text, marginBottom: 12 },
  existingCard: {
    backgroundColor: colors.primaryLight, borderRadius: 10, padding: 14,
    marginBottom: 16, borderWidth: 1, borderColor: colors.primary,
  },
  existingTitle: { fontSize: 15, fontWeight: "700", color: colors.primary },
  existingCount: { fontSize: 12, color: colors.textSecondary, marginTop: 4 },
  instructions: { fontSize: 14, color: colors.textSecondary, marginBottom: 16 },
  questionCard: {
    backgroundColor: colors.surface, borderRadius: 12, padding: 16,
    marginBottom: 12, borderWidth: 1, borderColor: colors.border,
  },
  category: { fontSize: 10, fontWeight: "700", color: colors.textTertiary, letterSpacing: 1, marginBottom: 4 },
  questionText: { fontSize: 14, fontWeight: "600", color: colors.text, marginBottom: 12 },
  selectorRow: { flexDirection: "row", justifyContent: "space-between", gap: 4 },
  scoreBtn: {
    flex: 1, paddingVertical: 8, borderRadius: 8,
    backgroundColor: colors.surfaceElevated, alignItems: "center",
  },
  scoreBtnActive: { backgroundColor: colors.primary },
  scoreBtnText: { fontSize: 13, fontWeight: "700", color: colors.textSecondary },
  scoreBtnTextActive: { color: "#fff" },
  submitBtn: {
    backgroundColor: colors.primary, borderRadius: 12, padding: 16,
    alignItems: "center", marginTop: 8,
  },
  submitBtnText: { color: "#fff", fontSize: 16, fontWeight: "800" },
  successCard: { alignItems: "center", paddingVertical: 40 },
  successIcon: { fontSize: 48, color: colors.success, marginBottom: 12 },
  successText: { fontSize: 18, fontWeight: "700", color: colors.success },
  backBtn: { marginTop: 20, padding: 12 },
  backBtnText: { fontSize: 15, color: colors.primary, fontWeight: "600" },
});
