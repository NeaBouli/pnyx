import React, { useCallback, useEffect, useRef, useState } from "react";
import { View, Text, Switch, StyleSheet, ScrollView, TouchableOpacity } from "react-native";
import * as SecureStore from "expo-secure-store";
import { colors } from "../theme";
import {
  markAllNotificationsRead,
  markNotificationCategoryRead,
} from "../lib/notifications";
import type { NotificationPreferenceKey } from "../lib/notification-preferences";

const SETTINGS = [
  { key: "push_vote_open", icon: "🗳️", label: "Νέες Ψηφοφορίες", sub: "Όταν ανοίγει νέα ψηφοφορία" },
  { key: "push_vote_24h", icon: "⏰", label: "24 Ώρες πριν το κλείσιμο", sub: "Υπενθύμιση για ψηφοφορίες που λήγουν" },
  { key: "push_vote_result", icon: "📊", label: "Αποτελέσματα", sub: "Όταν κλείνει ψηφοφορία + Δείκτης Απόκλισης" },
  { key: "push_bill_announced", icon: "🏛️", label: "Νέα Νομοσχέδια", sub: "Ανακοινώσεις από τη Βουλή" },
  { key: "push_weekly_digest", icon: "📋", label: "Εβδομαδιαία Ειδοποίηση", sub: "Κάθε Δευτέρα — σύνοψη εβδομάδας (Push)" },
  { key: "push_system_update", icon: "⚙️", label: "Ενημερώσεις Συστήματος", sub: "Σημαντικές ανακοινώσεις πλατφόρμας" },
];

type PendingAck =
  | { kind: "all" }
  | { kind: "categories"; keys: NotificationPreferenceKey[] };

function acknowledgementFor(master: boolean, prefs: Record<string, boolean>): PendingAck | null {
  if (!master) return { kind: "all" };
  const keys = SETTINGS.filter(item => prefs[item.key] === false).map(item => item.key as NotificationPreferenceKey);
  return keys.length ? { kind: "categories", keys } : null;
}

async function runAck(ack: PendingAck): Promise<void> {
  if (ack.kind === "all") return markAllNotificationsRead();
  for (const key of ack.keys) await markNotificationCategoryRead(key);
}

async function attemptAck(ack: PendingAck): Promise<boolean> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try { await runAck(ack); return true; }
    catch { /* One idempotent retry; never discard stored unread state. */ }
  }
  return false;
}

export default function NotificationSettingsScreen() {
  const [master, setMaster] = useState(true);
  const [prefs, setPrefs] = useState<Record<string, boolean>>({});
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [pendingAck, setPendingAck] = useState<PendingAck | null>(null);
  const [ackBusy, setAckBusy] = useState(false);
  const mountedRef = useRef(true);
  const loadEpoch = useRef(0);
  const operationBusy = useRef(false);
  const policy = useRef({ master: true, prefs: {} as Record<string, boolean> });

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; loadEpoch.current += 1; };
  }, []);

  const load = useCallback(async () => {
    const epoch = ++loadEpoch.current;
    const current = () => mountedRef.current && epoch === loadEpoch.current;
    setLoading(true);
    try {
      const m = await SecureStore.getItemAsync("push_master");
      const values: [string, string | null][] = [];
      for (const s of SETTINGS) {
        values.push([s.key, await SecureStore.getItemAsync(s.key)]);
      }
      // Hydrate only after every value was read: a partial read keeps the
      // screen disabled instead of flashing default-on switches.
      if (!current()) return;
      const p: Record<string, boolean> = {};
      for (const [k, v] of values) p[k] = v !== "false"; // default true
      // Persisted opt-outs also recover acknowledgement interrupted by leaving
      // the screen or terminating the app. Enabled categories stay untouched.
      const ack = acknowledgementFor(m !== "false", p);
      const acknowledged = ack ? await attemptAck(ack) : true;
      if (!current()) return;
      policy.current = { master: m !== "false", prefs: p };
      setMaster(m !== "false");
      setPrefs(p);
      setPendingAck(acknowledged ? null : ack);
      setLoaded(true);
      setLoadFailed(false);
    } catch {
      if (current()) {
        setLoaded(false);
        setLoadFailed(true);
      }
    } finally {
      if (current()) setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  // The persisted opt-out is kept even when the unread acknowledgement
  // fails: the acknowledgement gets one automatic retry, then surfaces an
  // explicit retry action while the saved preference stays untouched.
  const acknowledge = async () => {
    const ack = acknowledgementFor(policy.current.master, policy.current.prefs);
    const success = ack ? await attemptAck(ack) : true;
    if (mountedRef.current) setPendingAck(success ? null : ack);
  };

  const retryAck = async () => {
    if (operationBusy.current) return;
    // Never replay the old scope after a preference was re-enabled.
    const ack = acknowledgementFor(policy.current.master, policy.current.prefs);
    if (!ack) { if (mountedRef.current) setPendingAck(null); return; }
    operationBusy.current = true;
    setAckBusy(true);
    try {
      await runAck(ack);
      if (mountedRef.current) setPendingAck(null);
    } catch {
      // Stay pending; the retry action remains visible.
    } finally {
      operationBusy.current = false;
      if (mountedRef.current) setAckBusy(false);
    }
  };

  const toggleMaster = async (val: boolean) => {
    if (!loaded || operationBusy.current) return;
    operationBusy.current = true;
    setBusy(true);
    try {
      await SecureStore.setItemAsync("push_master", String(val));
      policy.current = { ...policy.current, master: val };
      if (mountedRef.current) { setMaster(val); setError(false); }
      await acknowledge();
    } catch {
      if (mountedRef.current) setError(true);
    } finally {
      operationBusy.current = false;
      if (mountedRef.current) setBusy(false);
    }
  };

  const togglePref = async (key: string, val: boolean) => {
    if (!loaded || !policy.current.master || operationBusy.current) return;
    operationBusy.current = true;
    setBusy(true);
    try {
      await SecureStore.setItemAsync(key, String(val));
      policy.current = { ...policy.current, prefs: { ...policy.current.prefs, [key]: val } };
      if (mountedRef.current) {
        setPrefs(prev => ({ ...prev, [key]: val }));
        setError(false);
      }
      // Other categories remain unread.
      await acknowledge();
    } catch {
      if (mountedRef.current) setError(true);
    } finally {
      operationBusy.current = false;
      if (mountedRef.current) setBusy(false);
    }
  };

  // Failed ledger writes must not lock the user's notification preferences.
  const switchesDisabled = !loaded || busy || ackBusy;

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      <View style={s.masterRow}>
        <View>
          <Text style={s.masterLabel}>Ειδοποιήσεις</Text>
          <Text style={s.masterSub}>Κύριος διακόπτης</Text>
        </View>
        <Switch value={master} disabled={switchesDisabled} onValueChange={toggleMaster} trackColor={{ true: colors.primary, false: colors.border }} thumbColor="#fff" />
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
            disabled={!master || switchesDisabled}
            trackColor={{ true: colors.primary, false: colors.border }}
            thumbColor="#fff"
          />
        </View>
      ))}

      {loadFailed ? (
        <View style={s.retryWrap}>
          <Text accessibilityRole="alert" style={s.errorText}>Αδυναμία φόρτωσης ρυθμίσεων.</Text>
          <TouchableOpacity style={s.retryBtn} onPress={load} disabled={loading}>
            <Text style={s.retryText}>Δοκιμάστε ξανά</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {pendingAck ? (
        <View style={s.retryWrap}>
          <Text accessibilityRole="alert" style={s.errorText}>Η σήμανση ως αναγνωσμένο απέτυχε — η επιλογή σας αποθηκεύτηκε.</Text>
          <TouchableOpacity style={s.retryBtn} onPress={retryAck} disabled={ackBusy}>
            <Text style={s.retryText}>Επανάληψη</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {error ? <Text accessibilityRole="alert" style={s.footer}>Αδυναμία αποθήκευσης. Δοκιμάστε ξανά.</Text> : null}
      <Text style={s.footer}>Οι ρυθμίσεις ειδοποιήσεων και ο μετρητής εικονιδίου αποθηκεύονται τοπικά στη συσκευή σας.</Text>
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
  retryWrap: { alignItems: "center", marginTop: 16 },
  errorText: { fontSize: 13, fontWeight: "700", color: colors.error, textAlign: "center" },
  retryBtn: { backgroundColor: colors.primary, paddingHorizontal: 20, paddingVertical: 10, borderRadius: 8, marginTop: 10 },
  retryText: { color: "#fff", fontWeight: "700" },
  footer: { fontSize: 11, color: colors.textTertiary, textAlign: "center", marginTop: 24 },
});
