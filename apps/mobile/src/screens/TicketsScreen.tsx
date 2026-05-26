import React, { useEffect, useState, useCallback } from "react";
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  ActivityIndicator, RefreshControl, Alert, Modal, TextInput,
} from "react-native";
import { isVerified, loadKeypair, loadNullifier, getOrDerivePolisKey, buildTicketSignedBytes, buildVoteSignedBytes, buildRegisterKeyMessage, derivePolisTicketNullifier, derivePolisVoteNullifier, bytesToHex, hexToBytes } from "../lib/crypto-native";
import { ed25519 } from "@noble/curves/ed25519.js";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
import { colors } from "../theme";
import {
  fetchPolisTickets, registerPolisKey, createPolisTicket, votePolisTicket,
  type PolisTicket,
} from "../lib/api";
import * as SecureStore from "expo-secure-store";

type Nav = StackNavigationProp<RootStackParams, "Tabs">;

const CATEGORIES = [
  { key: "all", label: "Όλα" },
  { key: "proposal", label: "Προτάσεις" },
  { key: "bug", label: "Σφάλματα" },
  { key: "vote", label: "Ψηφοφορίες" },
];

const CATEGORY_COLORS: Record<string, string> = {
  bug: colors.error, proposal: colors.primary, vote: colors.success,
};

const ERROR_LABELS: Record<string, string> = {
  SELF_VOTE: "Δεν μπορείτε να ψηφίσετε το δικό σας ticket.",
  DUPLICATE_VOTE: "Έχετε ήδη ψηφίσει αυτό το ticket.",
  DUPLICATE_TICKET: "Αυτό το ticket υπάρχει ήδη.",
  KEY_MISMATCH: "Το κλειδί POLIS δεν αντιστοιχεί στην ταυτότητά σας.",
  UNREGISTERED_KEY: "Πρέπει πρώτα να εγγράψετε το κλειδί σας.",
  MISSING_TITLE: "Ο τίτλος είναι υποχρεωτικός.",
  INVALID_SIGNATURE: "Σφάλμα υπογραφής.",
  TIMESTAMP_EXPIRED: "Η αίτηση έληξε. Δοκιμάστε ξανά.",
};

function friendlyError(msg: string): string {
  for (const [code, label] of Object.entries(ERROR_LABELS)) {
    if (msg.includes(code)) return label;
  }
  return msg;
}

function timeAgo(date: string): string {
  const diff = (Date.now() - new Date(date).getTime()) / 1000;
  if (diff < 60) return "τώρα";
  if (diff < 3600) return Math.floor(diff / 60) + "λ";
  if (diff < 86400) return Math.floor(diff / 3600) + "ω";
  return Math.floor(diff / 86400) + "μ";
}

export default function TicketsScreen() {
  const nav = useNavigation<Nav>();
  const [tickets, setTickets] = useState<PolisTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState("all");
  const [verified, setVerified] = useState(false);

  // Create modal
  const [showCreate, setShowCreate] = useState(false);
  const [createTitle, setCreateTitle] = useState("");
  const [createContent, setCreateContent] = useState("");
  const [createCategory, setCreateCategory] = useState("proposal");
  const [creating, setCreating] = useState(false);

  const loadTickets = useCallback(async () => {
    try {
      setError(false);
      const cat = filter === "all" ? undefined : filter;
      const data = await fetchPolisTickets(cat);
      setTickets(data.tickets);
    } catch {
      setError(true);
    }
  }, [filter]);

  useEffect(() => {
    isVerified().then(setVerified);
    loadTickets().finally(() => setLoading(false));
  }, [loadTickets]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadTickets();
    setRefreshing(false);
  }, [loadTickets]);

  const ensureRegistered = async (): Promise<{
    pkPolisHex: string;
    privateKey: Uint8Array;
    nullifierHash: string;
  } | null> => {
    const polisKey = await getOrDerivePolisKey();
    if (!polisKey) { Alert.alert("Σφάλμα", "Δεν βρέθηκε κλειδί POLIS."); return null; }

    const nullifierHash = await loadNullifier();
    if (!nullifierHash) { Alert.alert("Σφάλμα", "Δεν βρέθηκε nullifier."); return null; }

    // Check if already registered
    const registered = await SecureStore.getItemAsync("polis_registered");
    if (registered === polisKey.pkPolisHex) {
      return { pkPolisHex: polisKey.pkPolisHex, privateKey: polisKey.privateKey, nullifierHash };
    }

    // Register key
    const keypair = await loadKeypair();
    if (!keypair) { Alert.alert("Σφάλμα", "Δεν βρέθηκε κλειδί ταυτότητας."); return null; }

    const ts = Date.now();
    const regMsg = buildRegisterKeyMessage(polisKey.pkPolisHex, nullifierHash, ts);
    const regSig = bytesToHex(ed25519.sign(regMsg, hexToBytes(keypair.privateKeyHex)));

    try {
      await registerPolisKey({
        nullifier_hash: nullifierHash,
        pk_polis: polisKey.pkPolisHex,
        identity_signature: regSig,
        timestamp_ms: ts,
      });
      await SecureStore.setItemAsync("polis_registered", polisKey.pkPolisHex);
    } catch (e: any) {
      if (e.message?.includes("already_registered")) {
        await SecureStore.setItemAsync("polis_registered", polisKey.pkPolisHex);
      } else {
        Alert.alert("Σφάλμα Εγγραφής", friendlyError(e.message));
        return null;
      }
    }

    return { pkPolisHex: polisKey.pkPolisHex, privateKey: polisKey.privateKey, nullifierHash };
  };

  const handleCreate = async () => {
    if (!createTitle.trim() || createContent.trim().length < 10) return;
    setCreating(true);
    try {
      const reg = await ensureRegistered();
      if (!reg) { setCreating(false); return; }

      const ts = Date.now();
      const nullifier = derivePolisTicketNullifier(
        reg.privateKey, createCategory, createTitle.trim(), createContent.trim(),
      );
      const signedBytes = buildTicketSignedBytes(
        createCategory, createContent.trim(), createTitle.trim(),
        hexToBytes(reg.pkPolisHex), hexToBytes(nullifier), ts,
      );
      const sig = bytesToHex(ed25519.sign(signedBytes, reg.privateKey));

      await createPolisTicket({
        title: createTitle.trim(),
        content: createContent.trim(),
        category: createCategory,
        pk_polis: reg.pkPolisHex,
        ticket_nullifier: nullifier,
        signature: sig,
        timestamp_ms: ts,
        nullifier_hash: reg.nullifierHash,
      });

      setShowCreate(false);
      setCreateTitle("");
      setCreateContent("");
      await loadTickets();
    } catch (e: any) {
      Alert.alert("Σφάλμα", friendlyError(e.message));
    } finally {
      setCreating(false);
    }
  };

  const handleVote = async (ticketId: string, vote: "up" | "down") => {
    try {
      const reg = await ensureRegistered();
      if (!reg) return;

      const ts = Date.now();
      const nullifier = derivePolisVoteNullifier(reg.privateKey, ticketId);
      const signedBytes = buildVoteSignedBytes(
        ticketId, vote, hexToBytes(reg.pkPolisHex), hexToBytes(nullifier), ts,
      );
      const sig = bytesToHex(ed25519.sign(signedBytes, reg.privateKey));

      await votePolisTicket(ticketId, {
        vote,
        pk_polis: reg.pkPolisHex,
        vote_nullifier: nullifier,
        signature: sig,
        timestamp_ms: ts,
        nullifier_hash: reg.nullifierHash,
      });
      await loadTickets();
    } catch (e: any) {
      Alert.alert("Σφάλμα", friendlyError(e.message));
    }
  };

  const handleAction = () => {
    if (!verified) {
      Alert.alert(
        "Απαιτείται Επαλήθευση",
        "Για tickets χρειάζεστε επαλήθευση μέσω smartphone.",
        [
          { text: "Επαλήθευση →", onPress: () => nav.navigate("Verify") },
          { text: "Κλείσιμο", style: "cancel" },
        ],
      );
      return false;
    }
    return true;
  };

  if (loading) return (
    <View style={s.container}>
      <ActivityIndicator color={colors.primary} style={{ marginTop: 60 }} />
    </View>
  );

  if (error) return (
    <View style={[s.container, s.centerContent]}>
      <Text style={{ fontSize: 40, marginBottom: 12 }}>⚠️</Text>
      <Text style={s.errorText}>Αδυναμία σύνδεσης</Text>
      <TouchableOpacity style={s.retryBtn} onPress={() => { setLoading(true); loadTickets().finally(() => setLoading(false)); }}>
        <Text style={s.retryText}>Δοκιμάστε ξανά</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <View style={s.container}>
      {/* Banner */}
      <View style={s.banner}>
        <Text style={s.bannerText}>
          {verified
            ? "📋 Δημιουργήστε tickets και ψηφίστε με κρυπτογραφική υπογραφή."
            : "📱 Για tickets χρειάζεστε επαλήθευση smartphone"}
        </Text>
      </View>

      {/* Filters */}
      <View style={s.filterRow}>
        {CATEGORIES.map(f => (
          <TouchableOpacity key={f.key} style={[s.filterBtn, filter === f.key && s.filterActive]} onPress={() => setFilter(f.key)}>
            <Text style={[s.filterText, filter === f.key && s.filterTextActive]}>{f.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* New ticket button */}
      <TouchableOpacity style={s.newBtnFull} onPress={() => { if (handleAction()) setShowCreate(true); }}>
        <Text style={s.newBtnText}>+ Νέο Ticket</Text>
      </TouchableOpacity>

      <FlatList
        data={tickets}
        keyExtractor={t => t.id}
        contentContainerStyle={{ padding: 16 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
        renderItem={({ item }) => (
          <View style={[s.card, { borderLeftColor: CATEGORY_COLORS[item.category] || colors.textTertiary }]}>
            <View style={s.cardHeader}>
              <View style={[s.badge, { backgroundColor: (CATEGORY_COLORS[item.category] || colors.textTertiary) + "18" }]}>
                <Text style={[s.badgeText, { color: CATEGORY_COLORS[item.category] || colors.textTertiary }]}>{item.category}</Text>
              </View>
              <Text style={s.cardTime}>{item.created_at ? timeAgo(item.created_at) : ""}</Text>
            </View>
            <Text style={s.cardTitle}>{item.title}</Text>
            <View style={s.cardFooter}>
              <View style={s.voteRow}>
                <TouchableOpacity style={s.voteBtn} onPress={() => { if (handleAction()) handleVote(item.id, "up"); }}>
                  <Text style={s.voteBtnText}>👍 {item.up_votes}</Text>
                </TouchableOpacity>
                <TouchableOpacity style={s.voteBtn} onPress={() => { if (handleAction()) handleVote(item.id, "down"); }}>
                  <Text style={s.voteBtnText}>👎 {item.down_votes}</Text>
                </TouchableOpacity>
              </View>
              <Text style={s.handle}>{item.handle}</Text>
            </View>
          </View>
        )}
        ListEmptyComponent={
          <View style={s.centerContent}>
            <Text style={{ fontSize: 40, marginBottom: 12 }}>🎫</Text>
            <Text style={s.emptyTitle}>Δεν υπάρχουν tickets ακόμα</Text>
            <Text style={s.emptySub}>Δημιουργήστε το πρώτο ticket</Text>
          </View>
        }
      />

      {/* Create Ticket Modal */}
      <Modal visible={showCreate} transparent animationType="slide" onRequestClose={() => setShowCreate(false)}>
        <View style={s.modalOverlay}>
          <View style={s.modalCard}>
            <Text style={s.modalTitle}>Νέο Ticket</Text>

            <Text style={s.inputLabel}>Κατηγορία</Text>
            <View style={s.catRow}>
              {[{ k: "proposal", l: "Πρόταση" }, { k: "bug", l: "Σφάλμα" }, { k: "vote", l: "Ψηφοφορία" }].map(c => (
                <TouchableOpacity key={c.k} style={[s.catBtn, createCategory === c.k && s.catActive]} onPress={() => setCreateCategory(c.k)}>
                  <Text style={[s.catText, createCategory === c.k && s.catTextActive]}>{c.l}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={s.inputLabel}>Τίτλος</Text>
            <TextInput style={s.input} value={createTitle} onChangeText={setCreateTitle} placeholder="Σύντομος τίτλος..." maxLength={120} />

            <Text style={s.inputLabel}>Περιγραφή</Text>
            <TextInput style={[s.input, { height: 100, textAlignVertical: "top" }]} value={createContent} onChangeText={setCreateContent} placeholder="Περιγράψτε το θέμα..." multiline maxLength={2000} />

            <TouchableOpacity
              style={[s.submitBtn, (!createTitle.trim() || createContent.trim().length < 10) && { opacity: 0.4 }]}
              onPress={handleCreate}
              disabled={creating || !createTitle.trim() || createContent.trim().length < 10}
            >
              <Text style={s.submitText}>{creating ? "Υποβολή..." : "Υποβολή Ticket"}</Text>
            </TouchableOpacity>

            <TouchableOpacity style={{ marginTop: 12, alignItems: "center" }} onPress={() => setShowCreate(false)}>
              <Text style={{ color: colors.textSecondary, fontWeight: "600" }}>Ακύρωση</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  centerContent: { alignItems: "center", justifyContent: "center", paddingTop: 60 },
  banner: { backgroundColor: colors.primaryLight, paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.primary + "30" },
  bannerText: { fontSize: 12, color: colors.primary, fontWeight: "600" },
  filterRow: { flexDirection: "row", gap: 6, paddingHorizontal: 16, paddingVertical: 10, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  filterBtn: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: 16, backgroundColor: colors.surfaceElevated },
  filterActive: { backgroundColor: colors.primary },
  filterText: { fontSize: 12, fontWeight: "700", color: colors.textSecondary },
  filterTextActive: { color: "#fff" },
  newBtnFull: { backgroundColor: colors.primary, marginHorizontal: 16, marginVertical: 8, paddingVertical: 12, borderRadius: 12, alignItems: "center" },
  newBtnText: { color: "#fff", fontSize: 14, fontWeight: "800" },
  card: { backgroundColor: colors.surface, borderRadius: 12, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: colors.border, borderLeftWidth: 4 },
  cardHeader: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 6 },
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  badgeText: { fontSize: 10, fontWeight: "800" },
  cardTime: { marginLeft: "auto", fontSize: 10, color: colors.textTertiary },
  cardTitle: { fontSize: 14, fontWeight: "800", color: colors.text, marginBottom: 8 },
  cardFooter: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  voteRow: { flexDirection: "row", gap: 6 },
  voteBtn: { backgroundColor: colors.surfaceElevated, paddingHorizontal: 12, paddingVertical: 4, borderRadius: 12 },
  voteBtnText: { fontSize: 13, fontWeight: "700", color: colors.text },
  handle: { fontSize: 10, color: colors.textTertiary, fontFamily: "monospace" },
  errorText: { fontSize: 16, fontWeight: "700", color: colors.text, marginBottom: 12 },
  retryBtn: { backgroundColor: colors.primary, paddingHorizontal: 20, paddingVertical: 10, borderRadius: 10 },
  retryText: { color: "#fff", fontWeight: "700" },
  emptyTitle: { fontSize: 16, fontWeight: "800", color: colors.text, marginBottom: 4 },
  emptySub: { fontSize: 13, color: colors.textSecondary },
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "flex-end" },
  modalCard: { backgroundColor: colors.surface, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, maxHeight: "85%" },
  modalTitle: { fontSize: 20, fontWeight: "900", color: colors.text, marginBottom: 16, textAlign: "center" },
  inputLabel: { fontSize: 12, fontWeight: "700", color: colors.textSecondary, marginBottom: 4, marginTop: 12 },
  input: { borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 12, fontSize: 14, color: colors.text, backgroundColor: colors.surfaceElevated },
  catRow: { flexDirection: "row", gap: 8 },
  catBtn: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, backgroundColor: colors.surfaceElevated, borderWidth: 1, borderColor: colors.border },
  catActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  catText: { fontSize: 12, fontWeight: "700", color: colors.textSecondary },
  catTextActive: { color: "#fff" },
  submitBtn: { backgroundColor: colors.primary, paddingVertical: 14, borderRadius: 12, alignItems: "center", marginTop: 20 },
  submitText: { color: "#fff", fontSize: 15, fontWeight: "800" },
});
