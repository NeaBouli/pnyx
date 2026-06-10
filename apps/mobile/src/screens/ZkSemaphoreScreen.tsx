import React, { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import * as SecureStore from "expo-secure-store";
import { colors } from "../theme";
import { getRuntimeZkCapability, type ZkCapability } from "../lib/zkSemaphore";

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

  if (!capability) {
    return <View style={s.center}><ActivityIndicator color={colors.primary} /></View>;
  }

  const ready = capability.status === "ready";

  return (
    <View style={s.container}>
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
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: 20 },
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
});
