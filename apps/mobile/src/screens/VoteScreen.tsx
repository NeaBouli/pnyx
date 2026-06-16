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
import { submitVote, correctVote, fetchVoteStatus, fetchZkStatus, fetchZkScopeStatus, type ZkScopeStatus } from "../lib/api";
import { isDemoMode } from "../lib/demo";
import { colors } from "../theme";
import { submitZkOptInForBill, submitZkVoteWithPublishedRoot, verifyZkVoteWithPublishedRoot } from "../lib/zkCanaryFlow";
import { canShowPublicZkVoting, canSubmitPublicZkVote, publicZkVoteScopeForBill } from "../lib/zkPublicVoting";
import type { ZkServerStatus } from "../lib/zkSemaphoreCore";

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
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/^\s*-\s*/gm, "")
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

function votingStatusNotice(status: string, source: string) {
  if (status === "ANNOUNCED") {
    return {
      icon: "🏛️",
      title: "Η ψηφοφορία δεν έχει ξεκινήσει ακόμα",
      body: "Το θέμα έχει δημοσιευθεί για ενημέρωση. Η ψήφος θα ανοίξει όταν περάσει σε ενεργή κατάσταση.",
    };
  }
  if (status === "PARLIAMENT_VOTED") {
    return {
      icon: "🏛️",
      title: "Η ψηφοφορία στη Βουλή ολοκληρώθηκε",
      body: "Η κανονική ψήφος πολιτών έχει κλείσει. Μπορείτε να δείτε τα αποτελέσματα και τα επίσημα έγγραφα.",
    };
  }
  if (status === "OPEN_END") {
    return {
      icon: "⚖️",
      title: source === "DIAVGEIA" ? "Ανοιχτή αξιολόγηση απόφασης" : "Ανοιχτή κλίμακα συναίνεσης",
      body: source === "DIAVGEIA"
        ? "Δεν πρόκειται για κανονική ψηφοφορία ΝΑΙ/ΟΧΙ. Μπορείτε να βαθμολογήσετε πόσο συμφωνείτε με την απόφαση."
        : "Η κανονική ψήφος ΝΑΙ/ΟΧΙ έχει ολοκληρωθεί. Εδώ μπορείτε να βαθμολογήσετε τη συμφωνία σας με την απόφαση της Βουλής.",
    };
  }
  return null;
}

import { correctionBanner, officialDocumentLinks, resolveSource, isPdfUrl, sourceLabel } from "../lib/source-resolver";

export default function VoteScreen({ route, navigation }: Props) {
  const { billId, billTitle } = route.params;
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [summary, setSummary] = useState("");
  const [analysis, setAnalysis] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [officialText, setOfficialText] = useState("");
  const [officialDocs, setOfficialDocs] = useState<{ label: string; url: string }[]>([]);
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
  const [zkStatus, setZkStatus] = useState<ZkServerStatus | null>(null);
  const [zkScopeStatus, setZkScopeStatus] = useState<ZkScopeStatus | null>(null);
  const [zkOptedIn, setZkOptedIn] = useState(false);
  const [zkVerifiedChoice, setZkVerifiedChoice] = useState<string | null>(null);
  const [zkBusy, setZkBusy] = useState<"opt-in" | "verify" | "vote" | null>(null);
  const [zkResult, setZkResult] = useState<{ ok: boolean; title: string; detail: string } | null>(null);

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
          const resolved = resolveSource(d.official_source_url, d.forum_topic_url);
          setBillStatus(d.status);
          setBillGovernance(d.governance_level || "NATIONAL");
          setBillSource(source);
          setBillPill(readableText(d.pill_el) ? d.pill_el : "");
          setSourceUrl(resolved.url);
          setSourceKind(resolved.kind);
          if (readableText(d.summary_short_el)) setSummary(d.summary_short_el);
          if (readableText(d.analysis_el)) setAnalysis(d.analysis_el);
          setOfficialText(cleanOfficialText(d.summary_long_el));
          setOfficialDocs(officialDocumentLinks(d.summary_long_el));
        }
        const nullifier = await loadNullifier();
        if (nullifier && mounted) {
          const voteStatus = await fetchVoteStatus(nullifier, billId);
          if (!mounted) return;
          setHasVoted(voteStatus.has_voted);
          setIsCorrected(voteStatus.is_correction);
          if (voteStatus.vote) setSelected(voteStatus.vote);
        }
        fetchZkStatus()
          .then((status) => {
            if (mounted) setZkStatus(status);
          })
          .catch(() => {
            if (mounted) setZkStatus(null);
          });
        fetchZkScopeStatus(publicZkVoteScopeForBill(billId))
          .then((status) => {
            if (mounted) setZkScopeStatus(status);
          })
          .catch(() => {
            if (mounted) setZkScopeStatus(null);
          });
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

  function shortValue(value: string): string {
    if (value.length <= 18) return value;
    return `${value.slice(0, 10)}...${value.slice(-6)}`;
  }

  async function handleZkOptIn() {
    if (zkBusy) return;
    Alert.alert(
      "Semaphore ZK",
      "Η προαιρετική ZK διαδρομή θα κλειδώσει την κανονική ψήφο για αυτό το θέμα, ώστε να μην υπάρξει διπλή ψήφος. Συνέχεια;",
      [
        { text: "Άκυρο", style: "cancel" },
        {
          text: "Συνέχεια",
          style: "destructive",
          onPress: async () => {
            setZkBusy("opt-in");
            setZkResult(null);
            try {
              const result = await submitZkOptInForBill(billId);
              const scopeStatus = await fetchZkScopeStatus(publicZkVoteScopeForBill(billId)).catch(() => null);
              setZkOptedIn(true);
              setZkScopeStatus(scopeStatus);
              setZkVerifiedChoice(null);
              setZkResult({
                ok: true,
                title: "ZK opt-in ολοκληρώθηκε",
                detail: `commitment ${shortValue(result.commitment)} · id ${result.response.commitment_id}. Η κανονική ψήφος κλειδώθηκε για αυτό το θέμα.`,
              });
            } catch (error) {
              setZkResult({
                ok: false,
                title: "ZK opt-in απέτυχε",
                detail: error instanceof Error ? error.message : "unknown error",
              });
            } finally {
              setZkBusy(null);
            }
          },
        },
      ],
    );
  }

  async function handleZkVerify(choice: string) {
    if (zkBusy || !canSubmitPublicZkVote(zkScopeStatus)) return;
    setZkBusy("verify");
    setZkResult(null);
    setZkVerifiedChoice(null);
    try {
      const result = await verifyZkVoteWithPublishedRoot({
        voteScopeId: publicZkVoteScopeForBill(billId),
        voteCommitment: choice,
      });
      const mutationsRejected = Object.values(result.mutations).every((mutation) => mutation.proof_verified === false);
      const ok = result.real.proof_verified === true && mutationsRejected;
      setZkVerifiedChoice(ok ? choice : null);
      setZkResult({
        ok,
        title: ok ? "ZK proof verification πέρασε" : "ZK proof verification απέτυχε",
        detail: `real=${String(result.real.proof_verified)} · mutated=${mutationsRejected ? "rejected" : "accepted"} · members=${result.groupSize}`,
      });
    } catch (error) {
      setZkResult({
        ok: false,
        title: "ZK proof verification απέτυχε",
        detail: error instanceof Error ? error.message : "unknown error",
      });
    } finally {
      setZkBusy(null);
    }
  }

  async function handleZkVote(choice: string) {
    if (zkBusy || zkVerifiedChoice !== choice || !canSubmitPublicZkVote(zkScopeStatus)) return;
    Alert.alert(
      "Semaphore ZK",
      `Θα υποβληθεί ανώνυμη ZK ψήφος: ${choice}. Συνέχεια;`,
      [
        { text: "Άκυρο", style: "cancel" },
        {
          text: "Υποβολή",
          style: "destructive",
          onPress: async () => {
            setZkBusy("vote");
            setZkResult(null);
            try {
              const result = await submitZkVoteWithPublishedRoot({
                voteScopeId: publicZkVoteScopeForBill(billId),
                voteCommitment: choice,
              });
              setHasVoted(true);
              setSelected(choice);
              setZkResult({
                ok: result.accepted,
                title: result.accepted ? "ZK ψήφος έγινε αποδεκτή" : "ZK ψήφος δεν έγινε αποδεκτή",
                detail: `receipt ${result.receipt_id} · arweave_pending=${String(result.arweave_pending)} · verifier ${result.verifier_version}`,
              });
              Alert.alert("Επιτυχία ✓", "Η ανώνυμη ZK ψήφος καταγράφηκε.", [
                { text: "Αποτελέσματα", onPress: () => navigation.replace("Result", { billId, billTitle, fromVote: true }) },
              ]);
            } catch (error) {
              setZkResult({
                ok: false,
                title: "ZK ψήφος απέτυχε",
                detail: error instanceof Error ? error.message : "unknown error",
              });
            } finally {
              setZkBusy(null);
            }
          },
        },
      ],
    );
  }

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
  const correctionState = correctionBanner(billStatus, isCorrected);
  const canUsePillAsSummary = billSource !== "DIAVGEIA" && readableText(billPill);
  const summaryFallback = sourceUrl && sourceKind === "official"
    ? "Το επίσημο κείμενο συγχρονίζεται — διαθέσιμο σύντομα. Δείτε την επίσημη πηγή."
    : "Το επίσημο κείμενο συγχρονίζεται — διαθέσιμο σύντομα.";
  const summaryText = summary || (canUsePillAsSummary ? billPill : "") || summaryFallback;
  const statusNotice = billLoaded && !showVoteControls ? votingStatusNotice(billStatus, billSource) : null;
  const showPublicZkVoting = canShowPublicZkVoting({
    serverStatus: zkStatus,
    scopeStatus: zkScopeStatus,
    billStatus,
    billSource,
    billLoaded,
  });
  const publicZkVoteReady = canSubmitPublicZkVote(zkScopeStatus);

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
      ) : summaryText || analysis || officialText || officialDocs.length > 0 || billLoaded ? (
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
          ) : null}
          {officialText ? (
            <>
              <Text style={{ fontWeight: "700", color: "#1e40af", fontSize: 13, marginTop: 12, marginBottom: 6 }}>
                Επίσημο κείμενο
              </Text>
              <Text style={{ color: "#374151", fontSize: 13, lineHeight: 20 }}>{officialText}</Text>
            </>
          ) : null}
          {officialDocs.length > 0 ? (
            <>
              <Text style={{ fontWeight: "700", color: "#1e40af", fontSize: 13, marginTop: 12, marginBottom: 6 }}>
                Πλήρη έγγραφα
              </Text>
              {officialDocs.map((doc) => (
                <TouchableOpacity
                  key={doc.url}
                  onPress={() => Linking.openURL(doc.url)}
                  style={{ backgroundColor: "#dbeafe", borderRadius: 8, padding: 10, marginTop: 6 }}
                >
                  <Text style={{ color: "#1d4ed8", fontSize: 13, fontWeight: "700" }}>📄 {doc.label}</Text>
                  <Text style={{ color: "#60a5fa", fontSize: 11, marginTop: 2 }}>Άνοιγμα πλήρους PDF ↗</Text>
                </TouchableOpacity>
              ))}
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

      {statusNotice && (
        <View style={styles.statusNotice}>
          <Text style={styles.statusNoticeIcon}>{statusNotice.icon}</Text>
          <Text style={styles.statusNoticeTitle}>
            {statusNotice.title}
          </Text>
          <Text style={styles.statusNoticeBody}>
            {statusNotice.body}
          </Text>
        </View>
      )}

      {correctionState.visible && (
        <View style={{ backgroundColor: correctionState.style === "used" ? "#f0fdf4" : "#fef3c7", borderRadius: 12, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: correctionState.style === "used" ? "#86efac" : "#f59e0b" }}>
          <Text style={{ fontWeight: "700", color: correctionState.style === "used" ? "#166534" : "#92400e", fontSize: 13 }}>
            {correctionState.style === "used" ? "✅ " : "⚠️ "}{correctionState.text}
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

      {showPublicZkVoting && (
        <View style={styles.zkCard}>
          <Text style={styles.zkTitle}>Semaphore ZK Pilot</Text>
          <Text style={styles.zkBody}>
            Προαιρετική ανώνυμη ψήφος για αυτό το θέμα. Μετά το ZK opt-in η κανονική
            ψήφος κλειδώνει για το ίδιο θέμα, ώστε να μη γίνει διπλή ψήφος.
          </Text>
          {!publicZkVoteReady && (
            <Text style={styles.zkHint}>
              Μετά το opt-in θα δημοσιευτεί νέος ZK root για αυτό το θέμα πριν ενεργοποιηθεί η ανώνυμη ψήφος.
            </Text>
          )}
          <TouchableOpacity
            style={[styles.secondaryAction, (zkOptedIn || zkBusy !== null) && styles.voteButtonDisabled]}
            onPress={handleZkOptIn}
            disabled={zkOptedIn || zkBusy !== null}
          >
            <Text style={styles.secondaryActionText}>
              {zkBusy === "opt-in" ? "ZK opt-in..." : zkOptedIn ? "ZK opt-in ενεργό" : "1. ZK opt-in"}
            </Text>
          </TouchableOpacity>
          <View style={styles.zkChoices}>
            {VOTE_OPTIONS.map((opt) => (
              <View key={opt.key} style={styles.zkChoiceRow}>
                <Text style={styles.zkChoiceLabel}>{opt.icon} {opt.label}</Text>
                <View style={styles.zkChoiceActions}>
                  <TouchableOpacity
                    style={[styles.zkSmallButton, (!zkOptedIn || !publicZkVoteReady || zkBusy !== null) && styles.voteButtonDisabled]}
                    onPress={() => handleZkVerify(opt.key)}
                    disabled={!zkOptedIn || !publicZkVoteReady || zkBusy !== null}
                  >
                    <Text style={styles.zkSmallButtonText}>
                      {zkBusy === "verify" ? "..." : "Verify"}
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.zkSmallButton, styles.zkSubmitButton, (zkVerifiedChoice !== opt.key || !publicZkVoteReady || zkBusy !== null) && styles.voteButtonDisabled]}
                    onPress={() => handleZkVote(opt.key)}
                    disabled={zkVerifiedChoice !== opt.key || !publicZkVoteReady || zkBusy !== null}
                  >
                    <Text style={styles.zkSubmitText}>
                      {zkBusy === "vote" ? "..." : "Vote"}
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>
            ))}
          </View>
          {zkResult && (
            <View style={[styles.zkResult, zkResult.ok ? styles.zkResultOk : styles.zkResultFail]}>
              <Text style={styles.zkResultTitle}>{zkResult.title}</Text>
              <Text style={styles.zkResultText}>{zkResult.detail}</Text>
            </View>
          )}
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
  statusNotice: {
    backgroundColor: "#f1f5f9",
    borderRadius: 12,
    padding: 18,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#cbd5e1",
    alignItems: "center",
  },
  statusNoticeIcon: { fontSize: 32, marginBottom: 8 },
  statusNoticeTitle: {
    fontWeight: "700",
    color: "#475569",
    fontSize: 15,
    textAlign: "center",
    marginBottom: 6,
  },
  statusNoticeBody: {
    color: "#64748b",
    fontSize: 13,
    textAlign: "center",
    lineHeight: 18,
  },
  loadingOverlay: { alignItems: "center", marginTop: 24 },
  loadingText: { marginTop: 8, color: colors.textSecondary },
  resultsLink: { marginTop: 32, alignItems: "center" },
  resultsLinkText: { color: colors.primary, fontSize: 14 },
  zkCard: {
    backgroundColor: "#f5f3ff",
    borderRadius: 12,
    padding: 16,
    marginTop: 20,
    borderWidth: 1,
    borderColor: "#8b5cf6",
  },
  zkTitle: { color: "#5b21b6", fontSize: 15, fontWeight: "900", marginBottom: 8 },
  zkBody: { color: "#6d28d9", fontSize: 12, lineHeight: 18, marginBottom: 12 },
  zkHint: { color: "#6d28d9", fontSize: 11, lineHeight: 16, marginBottom: 12, fontWeight: "700" },
  secondaryAction: { borderColor: "#7c3aed", borderWidth: 1, borderRadius: 10, padding: 12, alignItems: "center", marginBottom: 12 },
  secondaryActionText: { color: "#6d28d9", fontWeight: "900", fontSize: 13 },
  zkChoices: { gap: 10 },
  zkChoiceRow: { backgroundColor: "#faf5ff", borderRadius: 10, padding: 10, borderWidth: 1, borderColor: "#ddd6fe" },
  zkChoiceLabel: { color: "#4c1d95", fontWeight: "800", fontSize: 13, marginBottom: 8 },
  zkChoiceActions: { flexDirection: "row", gap: 8 },
  zkSmallButton: { flex: 1, borderColor: "#7c3aed", borderWidth: 1, borderRadius: 8, padding: 10, alignItems: "center" },
  zkSmallButtonText: { color: "#6d28d9", fontWeight: "800", fontSize: 12 },
  zkSubmitButton: { backgroundColor: "#7c3aed" },
  zkSubmitText: { color: "#fff", fontWeight: "800", fontSize: 12 },
  zkResult: { marginTop: 12, borderRadius: 10, padding: 12, borderWidth: 1 },
  zkResultOk: { backgroundColor: "#f0fdf4", borderColor: "#22c55e" },
  zkResultFail: { backgroundColor: "#fef2f2", borderColor: "#ef4444" },
  zkResultTitle: { color: colors.text, fontSize: 13, fontWeight: "900", marginBottom: 4 },
  zkResultText: { color: colors.textSecondary, fontSize: 12, lineHeight: 18 },
});
