import React, { useEffect, useState } from "react";
import { View, Text, Switch, StyleSheet, ScrollView } from "react-native";
import * as SecureStore from "expo-secure-store";
import { colors } from "../theme";

const SETTINGS = [
  { key: "push_vote_open", icon: "🗳️", label: "Νέες Ψηφοφορίες", sub: "Όταν ανοίγει νέα ψηφοφορία" },
  { key: "push_vote_24h", icon: "⏰", label: "24 Ώρες πριν το κλείσιμο", sub: "Υπενθύμιση για ψηφοφορίες που λήγουν" },
  { key: "push_vote_result", icon: "📊", label: "Αποτελέσματα", sub: "Όταν κλείνει ψηφοφορία + Δείκτης Απόκλισης" },
  { key: "push_bill_announced", icon: "🏛️", label: "Νέα Νομοσχέδια", sub: "Ανακοινώσεις από τη Βουλή" },
  { key: "push_weekly_digest", icon: "📋", label: "Εβδομαδιαία Ανακεφαλαίωση", sub: "Κάθε Δευτέρα — σύνοψη εβδομάδας" },
  { key: "push_system_update", icon: "⚙️", label: "Ενημερώσεις Συστήματος", sub: "Σημαντικές ανακοινώσεις πλατφόρμας" },
];

export default function NotificationSettingsScreen() {
  const [master, setMaster] = useState(true);
  const [prefs, setPrefs] = useState<Record<string, boolean>>({});

  useEffect(() => {
    (async () => {
      const m = await SecureStore.getItemAsync("push_master");
      setMaster(m !== "false");
      const p: Record<string, boolean> = {};
      for (const s of SETTINGS) {
        const v = await SecureStore.getItemAsync(s.key);
        p[s.key] = v !== "false"; // default true
      }
      setPrefs(p);
    })();
  }, []);

  const toggleMaster = async (val: boolean) => {
    setMaster(val);
    await SecureStore.setItemAsync("push_master", String(val));
  };

  const togglePref = async (key: string, val: boolean) => {
    setPrefs(prev => ({ ...prev, [key]: val }));
    await SecureStore.setItemAsync(key, String(val));
  };

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      <View style={s.masterRow}>
        <View>
          <Text style={s.masterLabel}>Ειδοποιήσεις</Text>
          <Text style={s.masterSub}>Κύριος διακόπτης</Text>
        </View>
        <Switch value={master} onValueChange={toggleMaster} trackColor={{ true: colors.primary, false: colors.border }} thumbColor="#fff" />
      </View>

      <View style={[s.divider, !master && { opacity: 0.4 }]} />

      {SETTINGS.map(item => (
        <View key={item.key} style={[s.row, !master && { opacity: 0.4 }]}>
          <Text style={s.icon}>{item.icon}</Text>
          <View style={s.textWrap}>
            <Text style={s.label}>{item.label}</Text>
            <Text style={s.sub}>{item.sub}</Text>
          </View>
          <Switch
            value={master && (prefs[item.key] ?? true)}
            onValueChange={v => togglePref(item.key, v)}
            disabled={!master}
            trackColor={{ true: colors.primary, false: colors.border }}
            thumbColor="#fff"
          />
        </View>
      ))}

      <Text style={s.footer}>Οι ειδοποιήσεις αποθηκεύονται τοπικά στη συσκευή σας.</Text>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20 },
  masterRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 16 },
  masterLabel: { fontSize: 18, fontWeight: "900", color: colors.text },
  masterSub: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: 8 },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.border },
  icon: { fontSize: 22, marginRight: 12, width: 30 },
  textWrap: { flex: 1 },
  label: { fontSize: 14, fontWeight: "700", color: colors.text },
  sub: { fontSize: 11, color: colors.textSecondary, marginTop: 1 },
  footer: { fontSize: 11, color: colors.textTertiary, textAlign: "center", marginTop: 24 },
});
