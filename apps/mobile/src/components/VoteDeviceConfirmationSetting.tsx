import React, { useEffect, useRef, useState } from "react";
import { Alert, StyleSheet, Switch, Text, View } from "react-native";
import { loadNullifier } from "../lib/crypto-native";
import { confirmOnDevice, isVoteDeviceConfirmationEnabled, saveVoteDeviceConfirmation } from "../lib/vote-device-confirmation";
import { colors } from "../theme";

const label = "Επιβεβαίωση ψήφου στη συσκευή";

export default function VoteDeviceConfirmationSetting() {
  const [owner, setOwner] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const mounted = useRef(true);
  const changing = useRef(false);

  useEffect(() => {
    mounted.current = true;
    let active = true;
    async function load() {
      try {
        const identity = await loadNullifier();
        const current = identity ? await isVoteDeviceConfirmationEnabled(identity) : false;
        if (!active) return;
        setOwner(identity);
        setEnabled(current);
      } catch {
        if (active) setLoadFailed(true);
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; mounted.current = false; };
  }, []);

  async function change(value: boolean) {
    if (!owner || loading || changing.current) return;
    changing.current = true;
    setLoading(true);
    try {
      const confirmation = await confirmOnDevice("Επιβεβαιώστε την αλλαγή ρύθμισης");
      if (!mounted.current) return;
      if (confirmation === "denied") {
        Alert.alert("Ακυρώθηκε", "Η επιβεβαίωση της συσκευής δεν ολοκληρώθηκε.");
        return;
      }
      if (value && confirmation === "no_lock") {
        Alert.alert("Κλείδωμα οθόνης", "Ορίστε πρώτα PIN, μοτίβο ή κωδικό στις ρυθμίσεις της συσκευής.");
        return;
      }
      if (await loadNullifier() !== owner || !mounted.current) return;
      await saveVoteDeviceConfirmation(owner, value);
      if (mounted.current) setEnabled(value);
    } catch {
      if (mounted.current) Alert.alert("Σφάλμα", "Η ρύθμιση δεν αποθηκεύτηκε.");
    } finally {
      changing.current = false;
      if (mounted.current) setLoading(false);
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
        disabled={loading || !owner || loadFailed}
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
