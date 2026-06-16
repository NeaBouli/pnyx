import React, { useEffect, useState } from "react";
import { ActivityIndicator, Alert, ScrollView, Share, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import * as SecureStore from "expo-secure-store";
import { colors } from "../theme";
import { fetchZkStatus } from "../lib/api";
import { getRuntimeZkCapability, type ZkCapability } from "../lib/zkSemaphore";
import { combineZkCapabilityWithServer, type ZkServerStatus } from "../lib/zkSemaphoreCore";
import { submitZkOptInForBill, submitZkVoteWithPublishedRoot, verifyZkVoteWithPublishedRoot } from "../lib/zkCanaryFlow";
import {
  canShowZkCanaryOperator,
  canRunZkCanaryOptIn,
  canRunZkCanaryVote,
  ZK_CANARY_BILL_ID,
  ZK_CANARY_SCOPE_ID,
  ZK_CANARY_VOTE_COMMITMENT,
} from "../lib/zkCanaryOperator";
import {
  runZkSemaphoreSelfTest,
  type ZkSemaphoreSelfTestResult,
} from "../lib/zkSemaphoreSelfTest";

const OPT_IN_KEY = "zk_semaphore_v2_opt_in";

type CanaryStepResult = {
  ok: boolean;
  title: string;
  detail: string;
};

function capabilityTitle(capability: ZkCapability): string {
  if (capability.status === "ready") return "Έτοιμο για προαιρετική ενεργοποίηση";
  if (capability.status === "disabled") return "Δεν είναι ακόμη ενεργό";
  return "Δεν μπορεί να ενεργοποιηθεί σε αυτή τη συσκευή";
}

function capabilityReason(reason: string): string {
  if (reason.includes("feature flag")) {
    return "Η λειτουργία Semaphore ZK V2 δεν έχει ενεργοποιηθεί ακόμη για την εφαρμογή.";
  }
  if (reason.includes("server status is still loading")) {
    return "Γίνεται έλεγχος της κατάστασης ZK στον διακομιστή.";
  }
  if (reason.includes("server status could not be loaded")) {
    return "Δεν ήταν δυνατός ο έλεγχος της κατάστασης ZK στον διακομιστή.";
  }
  if (reason.includes("Expo Go")) {
    return "Το Expo Go δεν μπορεί να φορτώσει τα απαραίτητα native ZK modules.";
  }
  if (reason.includes("Android/iOS")) {
    return "Η δημιουργία ZK αποδείξεων υποστηρίζεται μόνο σε Android ή iOS συσκευές.";
  }
  if (reason.includes("Native Mopro/Semaphore prover")) {
    return "Η συσκευή ή η τρέχουσα έκδοση της εφαρμογής δεν διαθέτει τον απαραίτητο native Mopro/Semaphore prover.";
  }
  return reason;
}

export default function ZkSemaphoreScreen() {
  const [capability, setCapability] = useState<ZkCapability | null>(null);
  const [serverStatus, setServerStatus] = useState<ZkServerStatus | null>(null);
  const [serverStatusError, setServerStatusError] = useState<string | null>(null);
  const [optedIn, setOptedIn] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selfTestRunning, setSelfTestRunning] = useState(false);
  const [selfTest, setSelfTest] = useState<ZkSemaphoreSelfTestResult | null>(null);
  const [operatorUnlocked, setOperatorUnlocked] = useState(false);
  const [canaryRunning, setCanaryRunning] = useState<"opt-in" | "verify" | "vote" | null>(null);
  const [canaryVerified, setCanaryVerified] = useState(false);
  const [canaryResult, setCanaryResult] = useState<CanaryStepResult | null>(null);

  useEffect(() => {
    setCapability(getRuntimeZkCapability());
    SecureStore.getItemAsync(OPT_IN_KEY).then((value) => setOptedIn(value === "true"));
    fetchZkStatus()
      .then((status) => {
        setServerStatus(status);
        setServerStatusError(null);
      })
      .catch((error) => {
        setServerStatus(null);
        setServerStatusError(error instanceof Error ? error.message : "unknown");
      });
  }, []);

  async function enableOptIn() {
    if (!capability?.canOptIn) return;
    setSaving(true);
    await SecureStore.setItemAsync(OPT_IN_KEY, "true");
    setOptedIn(true);
    setSaving(false);
  }

  async function disableOptIn() {
    setSaving(true);
    await SecureStore.deleteItemAsync(OPT_IN_KEY);
    setOptedIn(false);
    setSaving(false);
  }

  async function runSelfTest() {
    if (selfTestRunning) return;
    setSelfTestRunning(true);
    setSelfTest(null);
    const result = await runZkSemaphoreSelfTest();
    setSelfTest(result);
    setSelfTestRunning(false);
  }

  async function shareSelfTestFixture() {
    if (!selfTest?.ok) return;
    await Share.share({
      title: "Ekklesia Semaphore Gate 0 fixture",
      message: JSON.stringify(selfTest.fixture, null, 2),
    });
  }

  function formatPreview(value: string): string {
    if (value.length <= 18) return value;
    return `${value.slice(0, 10)}...${value.slice(-6)}`;
  }

  async function runCanaryOptIn() {
    if (canaryRunning) return;
    Alert.alert(
      "Internal ZK Canary",
      `Θα δημιουργηθεί πραγματικό ZK opt-in μόνο για ${ZK_CANARY_BILL_ID}. Συνέχεια;`,
      [
        { text: "Άκυρο", style: "cancel" },
        {
          text: "Συνέχεια",
          style: "destructive",
          onPress: async () => {
            setCanaryRunning("opt-in");
            setCanaryResult(null);
            try {
              const result = await submitZkOptInForBill(ZK_CANARY_BILL_ID);
              setCanaryVerified(false);
              setCanaryResult({
                ok: true,
                title: "Canary opt-in ολοκληρώθηκε",
                detail: `commitment ${formatPreview(result.commitment)} · member ${formatPreview(result.memberHex)} · id ${result.response.commitment_id}`,
              });
            } catch (error) {
              setCanaryResult({
                ok: false,
                title: "Canary opt-in απέτυχε",
                detail: error instanceof Error ? error.message : "unknown error",
              });
            } finally {
              setCanaryRunning(null);
            }
          },
        },
      ],
    );
  }

  async function runCanaryVote() {
    if (canaryRunning) return;
    Alert.alert(
      "Internal ZK Canary",
      `Θα σταλεί πραγματική ZK ψήφος ${ZK_CANARY_VOTE_COMMITMENT} μόνο για ${ZK_CANARY_SCOPE_ID}. Συνέχεια;`,
      [
        { text: "Άκυρο", style: "cancel" },
        {
          text: "Συνέχεια",
          style: "destructive",
          onPress: async () => {
            setCanaryRunning("vote");
            setCanaryResult(null);
            try {
              const result = await submitZkVoteWithPublishedRoot({
                voteScopeId: ZK_CANARY_SCOPE_ID,
                voteCommitment: ZK_CANARY_VOTE_COMMITMENT,
              });
              setCanaryResult({
                ok: result.accepted,
                title: result.accepted ? "Canary ZK vote έγινε αποδεκτό" : "Canary ZK vote δεν έγινε αποδεκτό",
                detail: `receipt ${result.receipt_id} · arweave_pending=${String(result.arweave_pending)} · verifier ${result.verifier_version}`,
              });
            } catch (error) {
              setCanaryResult({
                ok: false,
                title: "Canary ZK vote απέτυχε",
                detail: error instanceof Error ? error.message : "unknown error",
              });
            } finally {
              setCanaryRunning(null);
            }
          },
        },
      ],
    );
  }

  async function runCanaryVerify() {
    if (canaryRunning) return;
    setCanaryRunning("verify");
    setCanaryVerified(false);
    setCanaryResult(null);
    try {
      const result = await verifyZkVoteWithPublishedRoot({
        voteScopeId: ZK_CANARY_SCOPE_ID,
        voteCommitment: ZK_CANARY_VOTE_COMMITMENT,
      });
      const mutationsRejected = Object.values(result.mutations).every((mutation) => mutation.proof_verified === false);
      const passed = result.real.proof_verified && mutationsRejected;
      setCanaryVerified(passed);
      setCanaryResult({
        ok: passed,
        title: passed ? "Canary proof verification πέρασε" : "Canary proof verification απέτυχε",
        detail: `real=${String(result.real.proof_verified)} · mutated=${mutationsRejected ? "rejected" : "accepted"} · members=${result.groupSize}`,
      });
    } catch (error) {
      setCanaryResult({
        ok: false,
        title: "Canary proof verification απέτυχε",
        detail: error instanceof Error ? error.message : "unknown error",
      });
    } finally {
      setCanaryRunning(null);
    }
  }

  if (!capability) {
    return <View style={s.center}><ActivityIndicator color={colors.primary} /></View>;
  }

  const effectiveCapability = combineZkCapabilityWithServer(capability, serverStatus, serverStatusError);
  const ready = effectiveCapability.status === "ready";
  // The self-test only checks the local native prover; it does not opt in or send a vote.
  const canRunSelfTest = capability.status !== "unsupported";
  const showCanaryOperator = canShowZkCanaryOperator({ serverStatus, operatorUnlocked });
  const canaryOptInReady = canRunZkCanaryOptIn({ serverStatus, capability: effectiveCapability, optedIn });
  const canaryVoteReady = canRunZkCanaryVote({ serverStatus, capability: effectiveCapability, optedIn });

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      <TouchableOpacity onLongPress={() => setOperatorUnlocked(true)} activeOpacity={0.9}>
        <Text style={s.title}>Semaphore ZK V2</Text>
      </TouchableOpacity>
      <Text style={s.subtitle}>
        Προαιρετική ανώνυμη ψήφος με δημόσια επαληθεύσιμη απόδειξη. Το τρέχον σύστημα
        Ed25519 παραμένει το κανονικό μονοπάτι. Το ZK ανοίγει μόνο ανά συγκεκριμένη ψηφοφορία.
      </Text>

      <View style={[s.card, ready ? s.readyCard : s.blockedCard]}>
        <Text style={s.cardTitle}>{capabilityTitle(effectiveCapability)}</Text>
        {effectiveCapability.reasons.map((reason) => (
          <Text key={reason} style={s.reason}>• {capabilityReason(reason)}</Text>
        ))}
        {!ready && (
          <Text style={s.note}>
            Το Semaphore ZK V2 παραμένει ανενεργό μέχρι να πληρούνται όλες οι τεχνικές
            προϋποθέσεις και να ενεργοποιηθεί για τη συγκεκριμένη ψηφοφορία. Μπορείτε να
            συνεχίσετε κανονικά με το τρέχον σύστημα ψηφοφορίας.
          </Text>
        )}
      </View>

      <View style={s.card}>
        <Text style={s.cardTitle}>Έλεγχος native prover</Text>
        <Text style={s.note}>
          Δημιουργεί μία δοκιμαστική Semaphore απόδειξη στη συσκευή και την επαληθεύει
          τοπικά. Δεν δημιουργεί ψήφο και δεν στέλνει δεδομένα στο ekklesia.
        </Text>
        <TouchableOpacity
          style={[s.secondaryBtn, (!canRunSelfTest || selfTestRunning) && s.btnDisabled]}
          onPress={runSelfTest}
          disabled={!canRunSelfTest || selfTestRunning}
        >
          <Text style={[s.secondaryText, (!canRunSelfTest || selfTestRunning) && s.disabledButtonText]}>
            {selfTestRunning ? "Εκτέλεση ελέγχου..." : "Έλεγχος Prover"}
          </Text>
        </TouchableOpacity>
        {selfTest && (
          <View style={[s.selfTestResult, selfTest.ok ? s.selfTestOk : s.selfTestFail]}>
            <Text style={s.selfTestTitle}>
              {selfTest.ok ? "✅ Native prover λειτουργεί" : "⚠️ Ο έλεγχος απέτυχε"}
            </Text>
            {selfTest.ok ? (
              <>
                <Text style={s.selfTestText}>
                  Απόδειξη επαληθεύτηκε σε {Math.round(selfTest.durationMs / 100) / 10}s ·
                  depth {selfTest.proofDepth} · members {selfTest.groupSize} · proof {selfTest.proofBytes} bytes
                </Text>
                <TouchableOpacity style={s.fixtureBtn} onPress={shareSelfTestFixture}>
                  <Text style={s.fixtureText}>Κοινοποίηση Gate 0 fixture</Text>
                </TouchableOpacity>
              </>
            ) : (
              <Text style={s.selfTestText}>{selfTest.error}</Text>
            )}
          </View>
        )}
      </View>

      <View style={s.statusRow}>
        <Text style={s.statusLabel}>Opt-in κατάσταση</Text>
        <Text style={[s.statusValue, optedIn ? s.enabled : s.disabled]}>
          {optedIn ? "Ενεργό" : "Ανενεργό"}
        </Text>
      </View>

      {optedIn ? (
        <TouchableOpacity style={s.secondaryBtn} onPress={disableOptIn} disabled={saving}>
          <Text style={s.secondaryText}>{saving ? "..." : "Απενεργοποίηση"}</Text>
        </TouchableOpacity>
      ) : (
        <TouchableOpacity style={[s.primaryBtn, !ready && s.btnDisabled]} onPress={enableOptIn} disabled={!ready || saving}>
          <Text style={s.primaryText}>{saving ? "..." : "Προαιρετική ενεργοποίηση"}</Text>
        </TouchableOpacity>
      )}

      {showCanaryOperator && (
        <View style={[s.card, s.operatorCard]}>
          <Text style={s.cardTitle}>Internal ZK Canary</Text>
          <Text style={s.note}>
            Μόνο για χειριστή. Εκτελεί πραγματικό opt-in και δοκιμαστική ZK ψήφο στο κρυφό
            scope {ZK_CANARY_SCOPE_ID}. Δεν εμφανίζεται όταν το canary flag είναι κλειστό.
          </Text>
          {!optedIn && (
            <Text style={s.reason}>• Ενεργοποιήστε πρώτα το προαιρετικό ZK opt-in πιο πάνω.</Text>
          )}
          {!serverStatus?.verifier_enabled && (
            <Text style={s.reason}>• Η ψήφος θα ενεργοποιηθεί μόνο όταν ανοίξει το verifier gate.</Text>
          )}
          {!canaryVerified && canaryVoteReady && (
            <Text style={s.reason}>• Πριν από την ψήφο πρέπει να περάσει ο verify-only έλεγχος.</Text>
          )}
          <TouchableOpacity
            style={[s.secondaryBtn, (!canaryOptInReady || canaryRunning !== null) && s.btnDisabled]}
            onPress={runCanaryOptIn}
            disabled={!canaryOptInReady || canaryRunning !== null}
          >
            <Text style={[s.secondaryText, (!canaryOptInReady || canaryRunning !== null) && s.disabledButtonText]}>
              {canaryRunning === "opt-in" ? "Canary opt-in..." : "1. Canary opt-in"}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[s.secondaryBtn, s.operatorVoteBtn, (!canaryVoteReady || canaryRunning !== null) && s.btnDisabled]}
            onPress={runCanaryVerify}
            disabled={!canaryVoteReady || canaryRunning !== null}
          >
            <Text style={[s.secondaryText, (!canaryVoteReady || canaryRunning !== null) && s.disabledButtonText]}>
              {canaryRunning === "verify" ? "Canary verify..." : "2. Canary verify proof"}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[s.primaryBtn, s.operatorVoteBtn, (!canaryVoteReady || !canaryVerified || canaryRunning !== null) && s.btnDisabled]}
            onPress={runCanaryVote}
            disabled={!canaryVoteReady || !canaryVerified || canaryRunning !== null}
          >
            <Text style={s.primaryText}>
              {canaryRunning === "vote" ? "Canary vote..." : `3. Canary vote ${ZK_CANARY_VOTE_COMMITMENT}`}
            </Text>
          </TouchableOpacity>
          {canaryResult && (
            <View style={[s.selfTestResult, canaryResult.ok ? s.selfTestOk : s.selfTestFail]}>
              <Text style={s.selfTestTitle}>{canaryResult.title}</Text>
              <Text style={s.selfTestText}>{canaryResult.detail}</Text>
            </View>
          )}
        </View>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 32 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background },
  title: { fontSize: 24, fontWeight: "900", color: colors.text, marginBottom: 8 },
  subtitle: { fontSize: 14, lineHeight: 20, color: colors.textSecondary, marginBottom: 20 },
  card: { borderRadius: 12, padding: 16, borderWidth: 1, marginBottom: 20 },
  readyCard: { backgroundColor: colors.successBg, borderColor: colors.success },
  blockedCard: { backgroundColor: colors.warningBg, borderColor: colors.warning },
  cardTitle: { fontSize: 16, fontWeight: "900", color: colors.text, marginBottom: 10 },
  reason: { fontSize: 13, lineHeight: 19, color: colors.textSecondary, marginBottom: 4 },
  note: { fontSize: 12, lineHeight: 18, color: colors.textTertiary, marginTop: 10, fontStyle: "italic" },
  statusRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  statusLabel: { fontSize: 14, color: colors.textSecondary, fontWeight: "700" },
  statusValue: { fontSize: 14, fontWeight: "900" },
  enabled: { color: colors.success },
  disabled: { color: colors.textTertiary },
  primaryBtn: { backgroundColor: colors.primary, borderRadius: 12, padding: 16, alignItems: "center" },
  btnDisabled: { backgroundColor: colors.border },
  primaryText: { color: "#fff", fontWeight: "900", fontSize: 15 },
  secondaryBtn: { borderColor: colors.primary, borderWidth: 1, borderRadius: 12, padding: 16, alignItems: "center" },
  secondaryText: { color: colors.primary, fontWeight: "900", fontSize: 15 },
  disabledButtonText: { color: colors.textTertiary },
  selfTestResult: { marginTop: 12, borderRadius: 10, padding: 12, borderWidth: 1 },
  selfTestOk: { backgroundColor: colors.successBg, borderColor: colors.success },
  selfTestFail: { backgroundColor: colors.errorBg, borderColor: colors.error },
  selfTestTitle: { color: colors.text, fontSize: 13, fontWeight: "900", marginBottom: 4 },
  selfTestText: { color: colors.textSecondary, fontSize: 12, lineHeight: 18 },
  fixtureBtn: { marginTop: 10, borderColor: colors.success, borderWidth: 1, borderRadius: 10, padding: 10, alignItems: "center" },
  fixtureText: { color: colors.success, fontSize: 12, fontWeight: "900" },
  operatorCard: { backgroundColor: "#f8fafc", borderColor: colors.primary },
  operatorVoteBtn: { marginTop: 10 },
});
