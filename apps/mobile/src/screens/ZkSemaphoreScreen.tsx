import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, Share, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import * as SecureStore from "expo-secure-store";
import { colors } from "../theme";
import { getRuntimeZkCapability, type ZkCapability } from "../lib/zkSemaphore";
import {
  runZkSemaphoreSelfTest,
  type ZkSemaphoreSelfTestResult,
} from "../lib/zkSemaphoreSelfTest";

const OPT_IN_KEY = "zk_semaphore_v2_opt_in";

function capabilityTitle(capability: ZkCapability): string {
  if (capability.status === "ready") return "Έτοιμο για προαιρετική ενεργοποίηση";
  if (capability.status === "disabled") return "Δεν είναι ακόμη ενεργό";
  return "Δεν μπορεί να ενεργοποιηθεί σε αυτή τη συσκευή";
}

function capabilityReason(reason: string): string {
  if (reason.includes("feature flag")) {
    return "Η λειτουργία Semaphore ZK V2 δεν έχει ενεργοποιηθεί ακόμη για την εφαρμογή.";
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
  const [optedIn, setOptedIn] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selfTestRunning, setSelfTestRunning] = useState(false);
  const [selfTest, setSelfTest] = useState<ZkSemaphoreSelfTestResult | null>(null);

  useEffect(() => {
    setCapability(getRuntimeZkCapability());
    SecureStore.getItemAsync(OPT_IN_KEY).then((value) => setOptedIn(value === "true"));
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

  if (!capability) {
    return <View style={s.center}><ActivityIndicator color={colors.primary} /></View>;
  }

  const ready = capability.status === "ready";
  const canRunSelfTest = capability.status !== "unsupported";

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      <Text style={s.title}>Semaphore ZK V2</Text>
      <Text style={s.subtitle}>
        Προαιρετική ανώνυμη ψήφος με δημόσια επαληθεύσιμη απόδειξη. Το τρέχον σύστημα
        Ed25519 παραμένει το κανονικό μονοπάτι και δεν αλλάζει.
      </Text>

      <View style={[s.card, ready ? s.readyCard : s.blockedCard]}>
        <Text style={s.cardTitle}>{capabilityTitle(capability)}</Text>
        {capability.reasons.map((reason) => (
          <Text key={reason} style={s.reason}>• {capabilityReason(reason)}</Text>
        ))}
        {!ready && (
          <Text style={s.note}>
            Το Semaphore ZK V2 παραμένει ανενεργό μέχρι να πληρούνται όλες οι τεχνικές
            προϋποθέσεις. Μπορείτε να συνεχίσετε κανονικά με το τρέχον σύστημα ψηφοφορίας.
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
});
