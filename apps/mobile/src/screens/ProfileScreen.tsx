import React, { useEffect, useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator } from "react-native";
import { Picker } from "@react-native-picker/picker";
import * as SecureStore from "expo-secure-store";
import { useNavigation } from "@react-navigation/native";
import type { StackNavigationProp } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
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

  useEffect(() => {
    (async () => {
      try {
        const API = process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr";
        const res = await fetch(`${API}/api/v1/periferia`);
        const data = await res.json();
        setPeriferias(data);
      } catch {}

      // Load saved preferences
      const savedP = await SecureStore.getItemAsync("user_periferia_id");
      const savedD = await SecureStore.getItemAsync("user_dimos_id");
      const savedL = await SecureStore.getItemAsync("user_language");
      if (savedP) setSelectedPeriferia(Number(savedP));
      if (savedD) setSelectedDimos(Number(savedD));
      if (savedL === "en") setLanguage("en");
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
    if (selectedPeriferia) await SecureStore.setItemAsync("user_periferia_id", String(selectedPeriferia));
    else await SecureStore.deleteItemAsync("user_periferia_id");
    if (selectedDimos) await SecureStore.setItemAsync("user_dimos_id", String(selectedDimos));
    else await SecureStore.deleteItemAsync("user_dimos_id");
    await SecureStore.setItemAsync("user_language", language);
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
      <Text style={s.subtitle}>Προαιρετικό — μπορείτε να αλλάξετε αργότερα</Text>

      {/* Info banner */}
      <View style={s.infoBanner}>
        <Text style={s.infoText}>ℹ️ Χωρίς δήλωση: μόνο Βουλή</Text>
        <Text style={s.infoText}>📍 Με Περιφέρεια: + Περιφερειακές αποφάσεις</Text>
        <Text style={s.infoText}>🏘️ Με Δήμο: + Δημοτικές αποφάσεις</Text>
        <Text style={s.infoTextSmall}>Διαβάζεις τα πάντα ανεξαρτήτως</Text>
      </View>

      {/* Periferia */}
      <Text style={s.sectionTitle}>Εκλογική Περιφέρεια (προαιρετικό)</Text>
      <View style={s.pickerWrap}>
        <Picker
          selectedValue={selectedPeriferia}
          onValueChange={v => { setSelectedPeriferia(v); setSelectedDimos(null); }}
          style={s.picker}
        >
          <Picker.Item label="Δεν δηλώνω" value={null} />
          {periferias.map(p => <Picker.Item key={p.id} label={p.name_el} value={p.id} />)}
        </Picker>
      </View>

      {/* Dimos */}
      {selectedPeriferia && dimoi.length > 0 && (
        <>
          <Text style={s.sectionTitle}>Δήμος (προαιρετικό)</Text>
          <View style={s.pickerWrap}>
            <Picker selectedValue={selectedDimos} onValueChange={setSelectedDimos} style={s.picker}>
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
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 40 },
  title: { fontSize: 24, fontWeight: "900", color: colors.text, marginBottom: 4 },
  subtitle: { fontSize: 13, color: colors.textSecondary, marginBottom: 20 },
  infoBanner: { backgroundColor: colors.primaryLight, borderRadius: 12, padding: 14, marginBottom: 20, borderWidth: 1, borderColor: colors.primary + "30" },
  infoText: { fontSize: 13, color: colors.primary, marginBottom: 3 },
  infoTextSmall: { fontSize: 11, color: colors.textSecondary, marginTop: 4, fontStyle: "italic" },
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
});
