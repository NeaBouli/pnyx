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
  Linking,
} from "react-native";
import * as LocalAuthentication from "expo-local-authentication";
import type { StackScreenProps } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
import { loadKeypair, loadNullifier, signVote, verifyVote } from "../lib/crypto-native";
import { submitVote, correctVote, fetchVoteStatus } from "../lib/api";
import { isDemoMode } from "../lib/demo";
import { colors } from "../theme";

type Props = StackScreenProps<RootStackParams, "Vote">;

const VOTE_OPTIONS = [
  { key: "YES", label: "ΝΑΙ", color: "#2e7d32", icon: "👍" },
  { key: "NO", label: "ΟΧΙ", color: "#c62828", icon: "👎" },
  { key: "ABSTAIN", label: "ΑΠΟΧΗ", color: "#f57f17", icon: "⏸️" },
] as const;

function readableText(value?: string | null) {
  return Boolean(value && value.trim() && !value.includes("[unknown:"));
}

function cleanOfficialText(value?: string | null) {
  if (!readableText(value)) return "";
  const cleaned = String(value)
    .replace(/\[[^\]]*\]\(https?:\/\/[^)]*\)/g, "")
    .replace(/\]\(/g, " ")
    .replace(/(^|\s)>\s*/g, "$1")
    .replace(/[*_`]+/g, "")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\s+/g, " ")
    .trim();
  const badPatterns = [
    "Μετάβαση στο κύριο περιεχόμενο",
    "Ανοίξτε το μενού προσβασιμότητας",
    "Νομοθετική Διαδικασία",
    "Ημερ. Διάταξη Ολομέλειας",
    "Εβδομαδιαίο Δελτίο",
    "Εμφανίζονται τα σχέδια",
    "Εμφανίζονται τα ψηφισθέντα",
    "Κατατεθέντα Σ/Ν",
  ];
  if (badPatterns.some(p => cleaned.includes(p))) {
    return "";
  }
  return cleaned.slice(0, 1400);
}

function isPdfUrl(url: string) {
  return url?.toLowerCase().includes(".pdf");
}

function sourceLabel(source: string, sourceKind: string, url: string) {
  if (source === "DIAVGEIA") return "Πηγή — Διαύγεια";
  if (sourceKind === "forum") return "Διαβάστε & συζητήστε στο Φόρουμ";
  if (isPdfUrl(url)) return "Πηγή — Βουλή (PDF)";
  return "Πηγή — Βουλή των Ελλήνων";
}

export default function VoteScreen({ route, navigation }: Props) {
  const { billId, billTitle } = route.params;
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [summary, setSummary] = useState("");
  const [analysis, setAnalysis] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [officialText, setOfficialText] = useState("");
  const [billStatus, setBillStatus] = useState<string>("");
  const [billLoaded, setBillLoaded] = useState(false);
  const [billGovernance, setBillGovernance] = useState<string>("NATIONAL");
  const [billSource, setBillSource] = useState<string>("PARLIAMENT");
  const [billPill, setBillPill] = useState<string>("");
  const [hasVoted, setHasVoted] = useState(false);
  const [isCorrected, setIsCorrected] = useState(false);
  const [consensusScore, setConsensusScore] = useState(0);
  const [consensusSubmitting, setConsensusSubmitting] = useState(false);
  const [consensusDone, setConsensusDone] = useState(false);
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceKind, setSourceKind] = useState<"official" | "forum" | "page" | "none">("none");

  React.useEffect(() => {
    const API = process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr";
    let mounted = true;
    (async () => {
      try {
        const r = await fetch(`${API}/api/v1/bills/${encodeURIComponent(billId)}`);
        const d = r.ok ? await r.json() : null;
        if (!mounted) return;
        if (d?.status) {
          const source = d.source || "PARLIAMENT";
          const officialUrl = d.official_source_url || "";
          const forumUrl = d.forum_topic_url || "";
          setBillStatus(d.status);
          setBillGovernance(d.governance_level || "NATIONAL");
          setBillSource(source);
          setBillPill(readableText(d.pill_el) ? d.pill_el : "");
          setSourceUrl(officialUrl || forumUrl);
          setSourceKind(officialUrl ? "official" : forumUrl ? "forum" : "none");
          if (readableText(d.summary_short_el)) setSummary(d.summary_short_el);
          if (d.ai_summary_reviewed && readableText(d.summary_long_el)) setAnalysis(d.summary_long_el);
          if (!d.ai_summary_reviewed) setOfficialText(cleanOfficialText(d.summary_long_el));
        }
        const nullifier = await loadNullifier();
        if (nullifier && mounted) {
          const voteStatus = await fetchVoteStatus(nullifier, billId);
          if (!mounted) return;
          setHasVoted(voteStatus.has_voted);
          setIsCorrected(voteStatus.is_correction);
          if (voteStatus.vote) setSelected(voteStatus.vote);
        }
      } catch {
        // Detail and vote-status failures must not block the screen.
      } finally {
        if (mounted) {
          setBillLoaded(true);
          setSummaryLoading(false);
        }
      }
    })();
    return () => { mounted = false; };
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
          [{ text: "Αποτελέσματα", onPress: () => navigation.replace("Result", { billId, billTitle, fromVote: true }) }]
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
      setHasVoted(true);
      setSelected(choice);

      Alert.alert("Επιτυχία ✓", res.message, [
        {
          text: "Αποτελέσματα",
          onPress: () => navigation.replace("Result", { billId, billTitle, fromVote: true }),
        },
      ]);
    } catch (err: any) {
      const message = err.message || "Η ψηφοφορία απέτυχε.";
      if (message.includes("ήδη") || message.includes("already") || message.includes("409")) {
        setHasVoted(true);
      }
      Alert.alert("Σφάλμα", message);
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
      setHasVoted(true);
      setSelected(choice);
      Alert.alert("Διόρθωση ✓", "Η ψήφος σας διορθώθηκε επιτυχώς.", [
        { text: "Αποτελέσματα", onPress: () => navigation.replace("Result", { billId, billTitle, fromVote: true }) },
      ]);
    } catch (err: any) {
      Alert.alert("Σφάλμα", err.message || "Η διόρθωση απέτυχε.");
    } finally {
      setLoading(false);
    }
  }

  const canCorrectVote = hasVoted && billStatus === "WINDOW_24H" && !isCorrected;
  const voteLocked = hasVoted && !canCorrectVote;
  const showVoteControls = billLoaded && (billStatus === "ACTIVE" || billStatus === "WINDOW_24H");
  const canUsePillAsSummary = billSource !== "DIAVGEIA" && readableText(billPill);
  const summaryFallback = sourceUrl && sourceKind === "official"
    ? "Το επίσημο κείμενο συγχρονίζεται — διαθέσιμο σύντομα. Δείτε την επίσημη πηγή."
    : "Το επίσημο κείμενο συγχρονίζεται — διαθέσιμο σύντομα.";
  const summaryText = summary || (canUsePillAsSummary ? billPill : "") || summaryFallback;

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ paddingBottom: 40 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
        <Text style={[styles.title, { flex: 1 }]}>{billTitle}</Text>
        <TouchableOpacity onPress={shareBill} style={{ padding: 8 }}>
          <Text style={{ fontSize: 22, color: colors.primary, fontWeight: "800" }}>↗</Text>
        </TouchableOpacity>
      </View>

      {sourceUrl && (sourceKind === "official" || sourceKind === "forum") ? (
        <TouchableOpacity
          onPress={() => Linking.openURL(sourceUrl)}
          style={{ backgroundColor: "#eff6ff", borderRadius: 10, padding: 12, marginBottom: 12, flexDirection: "row", alignItems: "center" }}
        >
          <Text style={{ fontSize: 14, marginRight: 8 }}>{sourceKind === "forum" ? "💬" : isPdfUrl(sourceUrl) ? "📄" : "🔗"}</Text>
          <View style={{ flex: 1 }}>
            <Text style={{ color: "#1d4ed8", fontSize: 13, fontWeight: "600" }}>{sourceLabel(billSource, sourceKind, sourceUrl)}</Text>
            {isPdfUrl(sourceUrl) && <Text style={{ color: "#93c5fd", fontSize: 11, marginTop: 2 }}>Ανοίγει ως έγγραφο PDF</Text>}
          </View>
          <Text style={{ color: "#93c5fd", fontSize: 12 }}>↗</Text>
        </TouchableOpacity>
      ) : billLoaded && billSource === "PARLIAMENT" ? (
        <View style={{ backgroundColor: "#f8fafc", borderRadius: 10, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: "#e2e8f0", flexDirection: "row", alignItems: "center" }}>
          <Text style={{ fontSize: 14, marginRight: 8 }}>🏛️</Text>
          <View style={{ flex: 1 }}>
            <Text style={{ color: "#475569", fontSize: 13, fontWeight: "600" }}>Πηγή — Βουλή των Ελλήνων</Text>
            <Text style={{ color: "#94a3b8", fontSize: 11, marginTop: 2 }}>Το κείμενο αναζητείται</Text>
          </View>
        </View>
      ) : null}

      {/* Reviewed summary/analysis */}
      {summaryLoading ? (
        <ActivityIndicator size="small" color={colors.textSecondary} style={{ marginBottom: 16 }} />
      ) : summaryText || analysis || officialText || billLoaded ? (
        <View style={{ backgroundColor: "#eff6ff", borderRadius: 12, padding: 14, marginBottom: 16 }}>
          <Text style={{ fontWeight: "700", color: "#1e40af", fontSize: 13, marginBottom: 6 }}>
            Σύνοψη
          </Text>
          <Text style={{ color: "#374151", fontSize: 13, lineHeight: 20 }}>
            {summaryText.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/).map((part, i) => {
              if (part.startsWith("**") && part.endsWith("**"))
                return <Text key={i} style={{ fontWeight: "700" }}>{part.slice(2, -2)}</Text>;
              if (part.startsWith("*") && part.endsWith("*"))
                return <Text key={i} style={{ fontStyle: "italic" }}>{part.slice(1, -1)}</Text>;
              return part;
            })}
          </Text>
          {analysis ? (
            <>
              <Text style={{ fontWeight: "700", color: "#1e40af", fontSize: 13, marginTop: 12, marginBottom: 6 }}>
                Ανάλυση
              </Text>
              <Text style={{ color: "#374151", fontSize: 13, lineHeight: 20 }}>{analysis}</Text>
            </>
          ) : officialText ? (
            <>
              <Text style={{ fontWeight: "700", color: "#1e40af", fontSize: 13, marginTop: 12, marginBottom: 6 }}>
                Επίσημο κείμενο
              </Text>
              <Text style={{ color: "#374151", fontSize: 13, lineHeight: 20 }}>{officialText}</Text>
              <Text style={{ color: "#64748b", fontSize: 11, lineHeight: 16, marginTop: 8 }}>
                Η πλήρης AI ανάλυση δεν έχει ακόμη ελεγχθεί. Εμφανίζεται απόσπασμα από την επίσημη πηγή.
              </Text>
            </>
          ) : null}
        </View>
      ) : null}

      {billGovernance !== "NATIONAL" && billGovernance !== "INSTITUTIONAL" && (
        <View style={{ backgroundColor: "#eff6ff", borderRadius: 12, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: "#2563eb" }}>
          <Text style={{ fontWeight: "700", color: "#1e40af", fontSize: 13 }}>
            📍 {billGovernance === "MUNICIPAL" ? "Δημοτική ψηφοφορία" : "Περιφερειακή ψηφοφορία"}
          </Text>
          <Text style={{ color: "#3b82f6", fontSize: 12, marginTop: 4 }}>
            Αφορά μόνο τους κατοίκους της περιοχής
          </Text>
        </View>
      )}

      {billGovernance === "INSTITUTIONAL" && billPill ? (
        <View style={{ backgroundColor: "#f5f3ff", borderRadius: 12, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: "#8b5cf6" }}>
          <Text style={{ fontWeight: "700", color: "#5b21b6", fontSize: 13 }}>
            🏢 {billPill}
          </Text>
        </View>
      ) : null}

      {billStatus === "ANNOUNCED" && (
        <View style={{ backgroundColor: "#f1f5f9", borderRadius: 12, padding: 20, marginBottom: 16, borderWidth: 1, borderColor: "#94a3b8", alignItems: "center" }}>
          <Text style={{ fontSize: 36, marginBottom: 8 }}>🏛️</Text>
          <Text style={{ fontWeight: "700", color: "#475569", fontSize: 15, textAlign: "center", marginBottom: 6 }}>
            Η ψηφοφορία δεν έχει ξεκινήσει ακόμα
          </Text>
          <Text style={{ color: "#64748b", fontSize: 13, textAlign: "center", lineHeight: 18 }}>
            Αυτό το νομοσχέδιο έχει ανακοινωθεί αλλά δεν είναι ακόμα ανοιχτό για ψηφοφορία. Θα ειδοποιηθείτε μόλις γίνει ενεργό.
          </Text>
        </View>
      )}

      {billStatus === "WINDOW_24H" && (
        <View style={{ backgroundColor: "#fef3c7", borderRadius: 12, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: "#f59e0b" }}>
          <Text style={{ fontWeight: "700", color: "#92400e", fontSize: 13 }}>
            ⚠️ Τελευταίες 24 ώρες — μπορείτε να διορθώσετε την ψήφο σας (μία φορά)
          </Text>
        </View>
      )}

      {showVoteControls && (
        <>
          <Text style={styles.info}>
            {canCorrectVote
              ? "Έχετε ήδη ψηφίσει. Μπορείτε να αλλάξετε την ψήφο σας μία φορά."
              : voteLocked
                ? "Έχετε ήδη ψηφίσει. Η ψήφος θα μπορεί να αλλάξει μόνο στο τελευταίο 24ωρο."
              : "Επιλέξτε την ψήφο σας. Απαιτείται βιομετρική πιστοποίηση."}
          </Text>

          <View style={styles.options}>
            {VOTE_OPTIONS.map((opt) => (
              <TouchableOpacity
                key={opt.key}
                style={[
                  styles.voteButton,
                  { borderColor: opt.color },
                  selected === opt.key && !voteLocked && { backgroundColor: opt.color },
                  voteLocked && styles.voteButtonDisabled,
                ]}
                onPress={() => canCorrectVote ? handleCorrection(opt.key) : handleVote(opt.key)}
                disabled={loading || voteLocked}
              >
                <Text style={styles.voteIcon}>{opt.icon}</Text>
                <Text
                  style={[
                    styles.voteLabel,
                    selected === opt.key && !voteLocked && { color: "#fff" },
                    voteLocked && styles.voteLabelDisabled,
                  ]}
                >
                  {opt.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </>
      )}

      {loading && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.loadingText}>Υποβολή ψήφου...</Text>
        </View>
      )}

      {/* Consensus Slider for OPEN_END Bills */}
      {billStatus === "OPEN_END" && !consensusDone && (
        <View style={{ backgroundColor: "#faf5ff", borderRadius: 12, padding: 16, marginTop: 24, borderWidth: 1, borderColor: "#a855f7" }}>
          <Text style={{ fontWeight: "800", color: "#5b21b6", fontSize: 14, marginBottom: 8 }}>
            ⚖️ Κλίμακα Συναίνεσης
          </Text>
          <Text style={{ fontSize: 12, color: "#7c3aed", marginBottom: 12 }}>
            {billSource === "DIAVGEIA" ? "Πόσο συμφωνείτε με αυτή την απόφαση;" : "Πόσο συμφωνείτε με την απόφαση της Βουλής;"}
          </Text>
          <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 4 }}>
            <Text style={{ fontSize: 10, color: "#ef4444" }}>Αντίσταση</Text>
            <Text style={{ fontSize: 10, color: "#94a3b8" }}>Ουδέτερο</Text>
            <Text style={{ fontSize: 10, color: "#22c55e" }}>Συναίνεση</Text>
          </View>
          <View style={{ flexDirection: "row", justifyContent: "center", flexWrap: "wrap", gap: 6, marginVertical: 8 }}>
            {[-5,-4,-3,-2,-1,0,1,2,3,4,5].map(v => (
              <TouchableOpacity key={v} onPress={() => setConsensusScore(v)}
                style={{ width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center",
                  backgroundColor: consensusScore === v ? (v > 0 ? "#22c55e" : v < 0 ? "#ef4444" : "#94a3b8") : "#f1f5f9",
                  borderWidth: consensusScore === v ? 2 : 1, borderColor: consensusScore === v ? "#7c3aed" : "#e2e8f0" }}>
                <Text style={{ fontSize: 12, fontWeight: "800", color: consensusScore === v ? "#fff" : "#64748b" }}>{v > 0 ? "+" : ""}{v}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={{ textAlign: "center", fontSize: 24, fontWeight: "900", color: consensusScore > 0 ? "#22c55e" : consensusScore < 0 ? "#ef4444" : "#94a3b8", marginVertical: 8 }}>
            {consensusScore > 0 ? "+" : ""}{consensusScore}
          </Text>
          <TouchableOpacity
            style={{ backgroundColor: "#7c3aed", borderRadius: 10, padding: 14, alignItems: "center" }}
            disabled={consensusSubmitting}
            onPress={async () => {
              setConsensusSubmitting(true);
              try {
                const nullifier = await loadNullifier();
                const keypair = await loadKeypair();
                if (!nullifier || !keypair) { Alert.alert("Σφάλμα", "Δεν έχετε επαληθευτεί"); return; }
                // Ed25519 Signatur: bill_id:score:nullifier_hash
                const sigParams = { bill_id: billId, vote: String(consensusScore), nullifier_hash: nullifier };
                const sigHex = signVote(keypair.privateKeyHex, sigParams);
                const API = process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr";
                const r = await fetch(`${API}/api/v1/vote/${encodeURIComponent(billId)}/consensus`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ score: consensusScore, nullifier_hash: nullifier, signature_hex: sigHex }),
                });
                if (r.ok) { setConsensusDone(true); Alert.alert("Ευχαριστούμε!", `Βαθμολογία: ${consensusScore > 0 ? "+" : ""}${consensusScore}`); }
                else { const d = await r.json(); Alert.alert("Σφάλμα", d.detail || "Αποτυχία"); }
              } catch (e: any) { Alert.alert("Σφάλμα", e.message); }
              finally { setConsensusSubmitting(false); }
            }}
          >
            <Text style={{ color: "#fff", fontWeight: "800", fontSize: 15 }}>
              {consensusSubmitting ? "..." : "Υποβολή Βαθμολογίας"}
            </Text>
          </TouchableOpacity>
        </View>
      )}
      {consensusDone && (
        <View style={{ backgroundColor: "#f0fdf4", borderRadius: 12, padding: 14, marginTop: 24, alignItems: "center" }}>
          <Text style={{ color: "#166534", fontWeight: "700" }}>✅ Η βαθμολογία σας καταγράφηκε</Text>
        </View>
      )}

      {billStatus !== "ANNOUNCED" && (
        <TouchableOpacity
          style={styles.resultsLink}
          onPress={() => navigation.navigate("Result", { billId, billTitle })}
        >
          <Text style={styles.resultsLinkText}>
            Δείτε τα τρέχοντα αποτελέσματα →
          </Text>
        </TouchableOpacity>
      )}
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
  voteButtonDisabled: {
    opacity: 0.45,
    borderColor: "#94a3b8",
  },
  voteIcon: { fontSize: 28, marginRight: 16 },
  voteLabel: { fontSize: 20, fontWeight: "bold", color: colors.text },
  voteLabelDisabled: { color: "#64748b" },
  loadingOverlay: { alignItems: "center", marginTop: 24 },
  loadingText: { marginTop: 8, color: colors.textSecondary },
  resultsLink: { marginTop: 32, alignItems: "center" },
  resultsLinkText: { color: colors.primary, fontSize: 14 },
});
