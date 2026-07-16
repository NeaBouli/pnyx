import React, { useEffect, useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, Linking, Share } from "react-native";
import { Picker } from "@react-native-picker/picker";
import * as SecureStore from "expo-secure-store";
import Constants from "expo-constants";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
import { resolveUpdateUrl } from "../lib/update-channel";
import { loadKeypair } from "../lib/crypto-native";
import {
  loadPendingProfileLocation,
  loadStoredProfileLocation,
  storeProfileLocation,
  syncProfileLocation,
} from "../lib/profile-location";
import { colors } from "../theme";

type Nav = StackNavigationProp<RootStackParams>;

interface Periferia { id: number; name_el: string; name_en: string; code: string }
interface Dimos { id: number; name_el: string; name_en: string; population: number }

export default function ProfileScreen() {
  const nav = useNavigation<Nav>();
  const [periferias, setPeriferias] = useState<Periferia[]>([]);
  const [dimoi, setDimoi] = useState<Dimos[]>([]);
  const [selectedPeriferia, setSelectedPeriferia] = useState<number | null>(null);
  const [selectedDimos, setSelectedDimos] = useState<number | null>(null);
  const [language, setLanguage] = useState<"el" | "en">("el");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [regionLocked, setRegionLocked] = useState(false);
  const [updateStatus, setUpdateStatus] = useState<"idle" | "checking" | "upToDate" | "updateAvailable">("idle");
  const [latestVersion, setLatestVersion] = useState<any>(null);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const API = process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr";
        const res = await fetch(`${API}/api/v1/periferia`);
        const data = await res.json();
        setPeriferias(data);
      } catch {}

      const nullifier = await SecureStore.getItemAsync("ekklesia_nullifier")
        || await SecureStore.getItemAsync("ekklesia:nullifier:v1");

      // Load only an unverified selection or a cache bound to this identity.
      const savedLocation = await loadStoredProfileLocation(nullifier);
      const savedL = await SecureStore.getItemAsync("user_language");
      if (savedLocation.periferiaId) setSelectedPeriferia(savedLocation.periferiaId);
      if (savedLocation.dimosId) setSelectedDimos(savedLocation.dimosId);
      if (savedL === "en") setLanguage("en");

      // Check region_locked from server
      try {
        if (nullifier) {
          const API = process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr";
          const statusRes = await fetch(`${API}/api/v1/identity/status`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nullifier_hash: nullifier }),
          });
          if (statusRes.ok) {
            const st = await statusRes.json();
            if (st.region_locked) setRegionLocked(true);
            const serverLocation = {
              periferiaId: st.periferia_id ?? null,
              dimosId: st.dimos_id ?? null,
            };
            if (serverLocation.periferiaId !== null || serverLocation.dimosId !== null) {
              await storeProfileLocation(serverLocation, nullifier);
              setSelectedPeriferia(serverLocation.periferiaId);
              setSelectedDimos(serverLocation.dimosId);
            } else {
              // A pre-verification selection is only a candidate. The newly
              // verified user must explicitly confirm it before the API locks it.
              const pendingLocation = await loadPendingProfileLocation();
              setSelectedPeriferia(pendingLocation.periferiaId);
              setSelectedDimos(pendingLocation.dimosId);
            }
          }
        }
      } catch {}

      setLoading(false);
    })();
  }, []);

  useEffect(() => {
    if (!selectedPeriferia) { setDimoi([]); setSelectedDimos(null); return; }
    const API = process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr";
    fetch(`${API}/api/v1/periferia/${selectedPeriferia}/dimos`)
      .then(r => r.json()).then(setDimoi).catch(() => setDimoi([]));
  }, [selectedPeriferia]);

  const save = async () => {
    setSaving(true);
    setSaveError("");
    await SecureStore.setItemAsync("user_language", language);

    // Sync location to server (enables vote scope enforcement)
    try {
      const nullifier = await SecureStore.getItemAsync("ekklesia_nullifier")
        || await SecureStore.getItemAsync("ekklesia:nullifier:v1");
      if (nullifier && !regionLocked) {
        const keypair = await loadKeypair();
        if (!keypair) throw new Error("Δεν βρέθηκε το κλειδί επαλήθευσης της συσκευής.");
        const data = await syncProfileLocation({
          nullifierHash: nullifier,
          privateKeyHex: keypair.privateKeyHex,
          selection: { periferiaId: selectedPeriferia, dimosId: selectedDimos },
        });
        setSelectedPeriferia(data.periferia_id);
        setSelectedDimos(data.dimos_id);
        if (data.region_locked) setRegionLocked(true);
      } else if (!nullifier) {
        // Unverified users may keep a read-only preference. Verification
        // discards it; a verified user must select and sign the scope again.
        await storeProfileLocation({
          periferiaId: selectedPeriferia,
          dimosId: selectedDimos,
        });
      }
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "Η γεωγραφική ρύθμιση δεν αποθηκεύτηκε.");
      setSaving(false);
      return;
    }

    await SecureStore.setItemAsync("user_profile_completed", "true");
    setSaving(false);
    nav.navigate("Tabs");
  };

  const skip = async () => {
    await SecureStore.setItemAsync("user_profile_completed", "true");
    nav.navigate("Tabs");
  };

  if (loading) return <View style={s.center}><ActivityIndicator color={colors.primary} /></View>;

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      <Text style={s.title}>Προφίλ</Text>
      <Text style={s.subtitle}>Προαιρετικό — η γεωγραφική δήλωση κλειδώνει μετά την επιβεβαίωση</Text>

      {/* Info banner */}
      <View style={s.infoBanner}>
        <Text style={s.infoText}>ℹ️ Χωρίς δήλωση: μόνο Βουλή</Text>
        <Text style={s.infoText}>📍 Με Περιφέρεια: + Περιφερειακές αποφάσεις</Text>
        <Text style={s.infoText}>🏘️ Με Δήμο: + Δημοτικές αποφάσεις</Text>
        <Text style={s.infoTextSmall}>Η εφαρμογή δείχνει τη Βουλή και μόνο τη δηλωμένη γεωγραφική εμβέλειά σας.</Text>
      </View>

      {/* Region Lock Warning */}
      {saveError ? <Text style={s.saveError}>{saveError}</Text> : null}
      {!regionLocked && (selectedPeriferia || selectedDimos) && (
        <View style={{ backgroundColor: "#fef3c7", borderRadius: 12, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: "#f59e0b" }}>
          <Text style={{ fontWeight: "700", color: "#92400e", fontSize: 12 }}>
            ⚠️ Προσοχή: Η δηλωμένη γεωγραφική περιοχή ορίζεται μία φορά και δεν μπορεί να αλλαχθεί.
          </Text>
        </View>
      )}
      {regionLocked && (
        <View style={{ backgroundColor: "#f0fdf4", borderRadius: 12, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: "#22c55e" }}>
          <Text style={{ fontWeight: "700", color: "#166534", fontSize: 12 }}>
            🔒 Η δηλωμένη γεωγραφική περιοχή έχει οριστεί και δεν μπορεί να αλλαχθεί.
          </Text>
        </View>
      )}

      {/* Periferia */}
      <Text style={s.sectionTitle}>Δηλωμένη Περιφέρεια {regionLocked ? "(κλειδωμένο)" : "(προαιρετικό)"}</Text>
      <View style={[s.pickerWrap, regionLocked && { opacity: 0.5 }]}>
        <Picker
          selectedValue={selectedPeriferia}
          onValueChange={v => { if (!regionLocked) { setSelectedPeriferia(v); setSelectedDimos(null); } }}
          style={s.picker}
          enabled={!regionLocked}
        >
          <Picker.Item label="Δεν δηλώνω" value={null} />
          {periferias.map(p => <Picker.Item key={p.id} label={p.name_el} value={p.id} />)}
        </Picker>
      </View>

      {/* Dimos */}
      {selectedPeriferia && dimoi.length > 0 && (
        <>
          <Text style={s.sectionTitle}>Δήμος {regionLocked ? "(κλειδωμένο)" : "(προαιρετικό)"}</Text>
          <View style={[s.pickerWrap, regionLocked && { opacity: 0.5 }]}>
            <Picker selectedValue={selectedDimos} onValueChange={v => { if (!regionLocked) setSelectedDimos(v); }} style={s.picker} enabled={!regionLocked}>
              <Picker.Item label="Δεν δηλώνω" value={null} />
              {dimoi.map(d => <Picker.Item key={d.id} label={d.name_el} value={d.id} />)}
            </Picker>
          </View>
        </>
      )}

      {/* Language */}
      <Text style={s.sectionTitle}>Γλώσσα / Language</Text>
      <View style={s.langRow}>
        <TouchableOpacity style={[s.langBtn, language === "el" && s.langActive]} onPress={() => setLanguage("el")}>
          <Text style={[s.langText, language === "el" && s.langTextActive]}>🇬🇷 Ελληνικά</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.langBtn, language === "en" && s.langActive]} onPress={() => setLanguage("en")}>
          <Text style={[s.langText, language === "en" && s.langTextActive]}>🇬🇧 English</Text>
        </TouchableOpacity>
      </View>

      {/* Buttons */}
      <TouchableOpacity style={s.saveBtn} onPress={save} disabled={saving}>
        <Text style={s.saveBtnText}>{saving ? "..." : "Αποθήκευση"}</Text>
      </TouchableOpacity>
      <TouchableOpacity style={s.skipBtn} onPress={skip}>
        <Text style={s.skipBtnText}>Αργότερα</Text>
      </TouchableOpacity>

      <TouchableOpacity style={s.zkBtn} onPress={() => nav.navigate("ZkSemaphore")}>
        <Text style={s.zkTitle}>Semaphore ZK V2</Text>
        <Text style={s.zkText}>
          Προαιρετικός έλεγχος συσκευής για ανώνυμη επαληθεύσιμη ψήφο όταν ενεργοποιηθεί σε συγκεκριμένη ψηφοφορία.
        </Text>
      </TouchableOpacity>

      <TouchableOpacity style={s.verifyBtn} onPress={() => nav.navigate("Verify")}>
        <Text style={s.verifyTitle}>Επαλήθευση / Νέο κλειδί</Text>
        <Text style={s.verifyText}>
          Για επανεγγραφή ή ελεγχόμενο operator canary. Χρησιμοποιεί HLR και αντικαθιστά το τοπικό κλειδί στη συσκευή.
        </Text>
      </TouchableOpacity>

      {/* Version + Channel + Update Check */}
      <Text style={s.versionInfo}>
        Έκδοση: {Constants.expoConfig?.version ?? "?"} (v{Constants.expoConfig?.android?.versionCode ?? "?"}) | Κανάλι: {Constants.expoConfig?.extra?.distributionChannel === "play" ? "Google Play" : "Direct"}
      </Text>
      <TouchableOpacity
        style={s.updateBtn}
        onPress={async () => {
          setUpdateStatus("checking");
          try {
            const API = process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr";
            const res = await fetch(`${API}/api/v1/app/version`);
            const data = await res.json();
            setLatestVersion(data);
            const current = Constants.expoConfig?.android?.versionCode ?? 0;
            setUpdateStatus(data.latest_version_code > current ? "updateAvailable" : "upToDate");
          } catch { setUpdateStatus("idle"); }
        }}
        disabled={updateStatus === "checking"}
      >
        {updateStatus === "checking" ? (
          <ActivityIndicator color={colors.primary} size="small" />
        ) : updateStatus === "upToDate" ? (
          <Text style={s.updateText}>✅ Τρέχουσα έκδοση</Text>
        ) : updateStatus === "updateAvailable" ? (
          <Text style={[s.updateText, { color: colors.success }]}>🆕 Νέα έκδοση διαθέσιμη!</Text>
        ) : (
          <Text style={s.updateText}>🔄 Έλεγχος ενημερώσεων</Text>
        )}
      </TouchableOpacity>
      {updateStatus === "updateAvailable" && latestVersion && (
        <TouchableOpacity
          style={s.downloadBtn}
          onPress={() => {
            try {
              const channel = Constants.expoConfig?.extra?.distributionChannel;
              const url = resolveUpdateUrl(latestVersion, channel);
              Linking.openURL(url);
            } catch {}
          }}
        >
          <Text style={s.downloadBtnText}>Λήψη έκδοσης {latestVersion.latest_version ?? "νέας"} →</Text>
        </TouchableOpacity>
      )}

      {/* Invite Friends */}
      <TouchableOpacity
        style={s.inviteBtn}
        onPress={async () => {
          try {
            await Share.share({
              message: "Ψήφισε ανώνυμα για τα νομοσχέδια της Βουλής!\nekklesia.gr — Ψηφιακή Άμεση Δημοκρατία\nΚατέβασε την εφαρμογή: https://ekklesia.gr/download",
            });
            fetch(`${process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr"}/api/v1/public/share`, { method: "POST" }).catch(() => {});
          } catch {}
        }}
      >
        <Text style={s.inviteBtnText}>Πρόσκληση Φίλων</Text>
      </TouchableOpacity>

      {/* Legal Links */}
      <View style={s.legalSection}>
        <TouchableOpacity onPress={() => Linking.openURL("https://ekklesia.gr/wiki/privacy.html")}>
          <Text style={s.legalLink}>Πολιτική Απορρήτου</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => Linking.openURL("https://ekklesia.gr/wiki/delete-account.html")}>
          <Text style={s.legalLink}>Διαγραφή Λογαριασμού</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => Linking.openURL("https://github.com/NeaBouli/pnyx")}>
          <Text style={s.legalLink}>Πηγαίος Κώδικας</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 120 },
  title: { fontSize: 24, fontWeight: "900", color: colors.text, marginBottom: 4 },
  subtitle: { fontSize: 13, color: colors.textSecondary, marginBottom: 20 },
  infoBanner: { backgroundColor: colors.primaryLight, borderRadius: 12, padding: 14, marginBottom: 20, borderWidth: 1, borderColor: colors.primary + "30" },
  infoText: { fontSize: 13, color: colors.primary, marginBottom: 3 },
  infoTextSmall: { fontSize: 11, color: colors.textSecondary, marginTop: 4, fontStyle: "italic" },
  saveError: { color: colors.error, backgroundColor: colors.errorBg, borderRadius: 8, padding: 10, marginBottom: 12, fontSize: 12, fontWeight: "700" },
  sectionTitle: { fontSize: 14, fontWeight: "800", color: colors.text, marginTop: 16, marginBottom: 8 },
  pickerWrap: { backgroundColor: colors.surface, borderRadius: 10, borderWidth: 1, borderColor: colors.border, overflow: "hidden", marginBottom: 8 },
  picker: { color: colors.text },
  langRow: { flexDirection: "row", gap: 10, marginBottom: 8 },
  langBtn: { flex: 1, padding: 12, backgroundColor: colors.surface, borderRadius: 10, alignItems: "center", borderWidth: 1, borderColor: colors.border },
  langActive: { backgroundColor: colors.primaryLight, borderColor: colors.primary },
  langText: { fontSize: 14, fontWeight: "700", color: colors.textSecondary },
  langTextActive: { color: colors.primary },
  saveBtn: { backgroundColor: colors.primary, borderRadius: 12, padding: 16, alignItems: "center", marginTop: 24 },
  saveBtnText: { color: "#fff", fontWeight: "800", fontSize: 16 },
  skipBtn: { alignItems: "center", padding: 14, marginTop: 8 },
  skipBtnText: { color: colors.textSecondary, fontWeight: "600", fontSize: 14 },
  versionInfo: { textAlign: "center", color: colors.textSecondary, fontSize: 11, marginTop: 24 },
  updateBtn: { alignItems: "center", padding: 10, marginTop: 8 },
  updateText: { fontSize: 13, fontWeight: "600", color: colors.primary },
  downloadBtn: { backgroundColor: colors.success, borderRadius: 10, padding: 12, alignItems: "center", marginTop: 8 },
  downloadBtnText: { color: "#fff", fontWeight: "700", fontSize: 14 },
  inviteBtn: { backgroundColor: colors.primaryLight, borderRadius: 12, padding: 14, alignItems: "center", marginTop: 24, borderWidth: 2, borderColor: colors.primary },
  inviteBtnText: { color: colors.primary, fontWeight: "800", fontSize: 15 },
  zkBtn: { backgroundColor: colors.surface, borderRadius: 12, padding: 14, marginTop: 16, borderWidth: 1, borderColor: colors.border },
  zkTitle: { color: colors.text, fontWeight: "900", fontSize: 15, marginBottom: 4 },
  zkText: { color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  verifyBtn: { backgroundColor: "#fff7ed", borderRadius: 12, padding: 14, marginTop: 12, borderWidth: 1, borderColor: "#fb923c" },
  verifyTitle: { color: "#9a3412", fontWeight: "900", fontSize: 15, marginBottom: 4 },
  verifyText: { color: "#9a3412", fontSize: 12, lineHeight: 17 },
  legalSection: { marginTop: 24, paddingTop: 16, borderTopWidth: 1, borderTopColor: colors.border, gap: 8, alignItems: "center" },
  legalLink: { fontSize: 13, color: colors.primary, fontWeight: "600" },
});
