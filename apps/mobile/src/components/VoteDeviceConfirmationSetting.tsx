import React, { useCallback, useRef, useState } from "react";
import { Alert, StyleSheet, Switch, Text, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { loadNullifier, subscribeIdentityChanges } from "../lib/crypto-native";
import { confirmOnDevice, isVoteDeviceConfirmationEnabled, saveVoteDeviceConfirmation } from "../lib/vote-device-confirmation";
import { colors } from "../theme";

const label = "Επιβεβαίωση ψήφου στη συσκευή";

export default function VoteDeviceConfirmationSetting() {
  const [owner, setOwner] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const focused = useRef(false);
  const revision = useRef(0);
  const changing = useRef(false);

  const load = useCallback(async () => {
    const currentRevision = ++revision.current;
    const current = () => focused.current && revision.current === currentRevision;
    setLoading(true);
    try {
      const identity = await loadNullifier();
      const required = identity ? await isVoteDeviceConfirmationEnabled(identity) : false;
      if (!current()) return;
      setOwner(identity);
      setEnabled(required);
      setLoadFailed(false);
    } catch {
      if (current()) setLoadFailed(true);
    } finally {
      if (current()) setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => {
    focused.current = true;
    setSaving(changing.current);
    const unsubscribe = subscribeIdentityChanges(() => { void load(); });
    void load();
    return () => {
      focused.current = false;
      revision.current++;
      unsubscribe();
    };
  }, [load]));

  async function change(value: boolean) {
    if (!focused.current || !owner || loading || loadFailed || changing.current) return;
    const currentRevision = revision.current;
    const current = () => focused.current && revision.current === currentRevision;
    changing.current = true;
    setSaving(true);
    try {
      const confirmation = await confirmOnDevice("Επιβεβαιώστε την αλλαγή ρύθμισης");
      if (!current()) return;
      if (confirmation === "denied") {
        Alert.alert("Ακυρώθηκε", "Η επιβεβαίωση της συσκευής δεν ολοκληρώθηκε.");
        return;
      }
      if (value && confirmation === "no_lock") {
        Alert.alert("Κλείδωμα οθόνης", "Ορίστε πρώτα PIN, μοτίβο ή κωδικό στις ρυθμίσεις της συσκευής.");
        return;
      }
      if (await loadNullifier() !== owner || !current()) return;
      await saveVoteDeviceConfirmation(owner, value);
      if (focused.current) await load();
    } catch {
      if (current()) Alert.alert("Σφάλμα", "Η ρύθμιση δεν αποθηκεύτηκε.");
    } finally {
      changing.current = false;
      if (focused.current) setSaving(false);
    }
  }

  return (
    <View style={styles.row}>
      <View style={styles.copy}>
        <Text style={styles.label}>{label}</Text>
        <Text style={styles.description}>
          {loadFailed
            ? "Η ρύθμιση δεν φορτώθηκε. Ανοίξτε ξανά τις Ρυθμίσεις."
            : !loading && !owner
              ? "Διαθέσιμο μετά την επαλήθευση ταυτότητας."
              : "PIN, μοτίβο ή βιομετρικά για κανονικές ψήφους και διορθώσεις."}
        </Text>
      </View>
      <Switch
        accessibilityLabel={label}
        disabled={loading || saving || !owner || loadFailed}
        value={enabled}
        onValueChange={change}
        trackColor={{ true: colors.primary, false: colors.border }}
        thumbColor="#fff"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 16, borderBottomWidth: 1, borderBottomColor: colors.border },
  copy: { flex: 1, marginRight: 12 },
  label: { color: colors.text, fontSize: 16, fontWeight: "700" },
  description: { color: colors.textSecondary, fontSize: 12, marginTop: 4 },
});
