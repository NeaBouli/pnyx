/**
 * OnboardingScreen — 5 Screens für neue User
 * Erklärt Konzept, setzt optional Dimos, startet Verifizierung
 */
import React, { useState, useRef, useEffect } from "react";
import {
  View, Text, StyleSheet, TouchableOpacity, FlatList,
  Dimensions, Image, ActivityIndicator,
} from "react-native";
import { Picker } from "@react-native-picker/picker";
import * as SecureStore from "expo-secure-store";
import type { StackScreenProps } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
import { colors } from "../theme";

const { width } = Dimensions.get("window");

type Props = StackScreenProps<RootStackParams, "Onboarding">;

interface Periferia { id: number; name_el: string }
interface Dimos { id: number; name_el: string }

const API = process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr";

export default function OnboardingScreen({ navigation }: Props) {
  const [current, setCurrent] = useState(0);
  const flatRef = useRef<FlatList>(null);

  // Screen 4: Dimos picker state
  const [periferias, setPeriferias] = useState<Periferia[]>([]);
  const [dimoi, setDimoi] = useState<Dimos[]>([]);
  const [selPeriferia, setSelPeriferia] = useState<number | null>(null);
  const [selDimos, setSelDimos] = useState<number | null>(null);

  useEffect(() => {
    fetch(`${API}/api/v1/periferia`)
      .then(r => r.json()).then(setPeriferias).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selPeriferia) { setDimoi([]); return; }
    fetch(`${API}/api/v1/periferia/${selPeriferia}/dimos`)
      .then(r => r.json()).then(setDimoi).catch(() => setDimoi([]));
  }, [selPeriferia]);

  const complete = async () => {
    // Save dimos if selected
    if (selPeriferia) await SecureStore.setItemAsync("user_periferia_id", String(selPeriferia));
    if (selDimos) await SecureStore.setItemAsync("user_dimos_id", String(selDimos));
    await SecureStore.setItemAsync("onboarding_completed", "true");

    // Sync to server if nullifier exists
    try {
      const nullifier = await SecureStore.getItemAsync("ekklesia:nullifier:v1");
      if (nullifier && (selPeriferia || selDimos)) {
        await fetch(`${API}/api/v1/identity/profile/location`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            nullifier_hash: nullifier,
            periferia_id: selPeriferia || 0,
            dimos_id: selDimos || 0,
          }),
        });
      }
    } catch {}

    navigation.replace("Tabs");
  };

  const goVerify = async () => {
    await SecureStore.setItemAsync("onboarding_completed", "true");
    navigation.replace("Verify");
  };

  const next = () => {
    if (current < 4) {
      flatRef.current?.scrollToIndex({ index: current + 1, animated: true });
      setCurrent(current + 1);
    }
  };

  const skip = async () => {
    await SecureStore.setItemAsync("onboarding_completed", "true");
    navigation.replace("Tabs");
  };

  const screens = [
    // Screen 1: Welcome
    <View key="1" style={[s.screen, { backgroundColor: "#eff6ff" }]}>
      <Image source={require("../../assets/pnx.png")} style={s.logo} />
      <Text style={s.title}>εκκλησία</Text>
      <Text style={s.subtitle}>του έθνους</Text>
      <Text style={s.tagline}>Η φωνή σου μετράει.</Text>
      <Text style={s.desc}>
        Ψηφιακή Άμεση Δημοκρατία{"\n"}για τον Έλληνα Πολίτη
      </Text>
      <TouchableOpacity style={s.ctaBtn} onPress={next}>
        <Text style={s.ctaBtnText}>Ξεκινήστε →</Text>
      </TouchableOpacity>
    </View>,

    // Screen 2: What is it
    <View key="2" style={s.screen}>
      <Text style={s.icon}>🏛️</Text>
      <Text style={s.title}>Τι είναι η εκκλησία;</Text>
      <Text style={s.desc}>
        Ψηφίστε σε πραγματικά νομοσχέδια{"\n"}
        της Βουλής, Περιφερειών και Δήμων.
      </Text>
      <View style={s.bullets}>
        <Text style={s.bullet}>🗳️ Βουλή — Εθνικά νομοσχέδια</Text>
        <Text style={s.bullet}>🏘️ Δήμοι — Τοπικές αποφάσεις (Διαύγεια)</Text>
        <Text style={s.bullet}>📊 Δείκτης Απόκλισης — Βουλή vs Πολίτες</Text>
      </View>
      <TouchableOpacity style={s.ctaBtn} onPress={next}>
        <Text style={s.ctaBtnText}>Επόμενο →</Text>
      </TouchableOpacity>
    </View>,

    // Screen 3: How it works
    <View key="3" style={s.screen}>
      <Text style={s.icon}>🔐</Text>
      <Text style={s.title}>Πώς λειτουργεί;</Text>
      <View style={s.bullets}>
        <Text style={s.bullet}>📱 SMS επαλήθευση (αριθμός ΠΟΤΕ δεν αποθηκεύεται)</Text>
        <Text style={s.bullet}>🔑 Ed25519 κρυπτογραφικό κλειδί (μόνο στη συσκευή σου)</Text>
        <Text style={s.bullet}>🗳️ Ψήφισε ανώνυμα με κρυπτογραφική υπογραφή</Text>
        <Text style={s.bullet}>📊 Δες τα αποτελέσματα σε πραγματικό χρόνο</Text>
      </View>
      <View style={s.disclaimer}>
        <Text style={s.disclaimerText}>
          ⚠️ Αυτή η πλατφόρμα δεν είναι κρατική υπηρεσία.{"\n"}
          Οι ψηφοφορίες δεν έχουν νομική δεσμευτικότητα.{"\n"}
          Πρωτοβουλία πολιτών για διαφάνεια και δημοκρατική εκπαίδευση.
        </Text>
      </View>
      <TouchableOpacity style={s.ctaBtn} onPress={next}>
        <Text style={s.ctaBtnText}>Επόμενο →</Text>
      </TouchableOpacity>
    </View>,

    // Screen 4: Dimos
    <View key="4" style={s.screen}>
      <Text style={s.icon}>📍</Text>
      <Text style={s.title}>Ο Δήμος σου</Text>
      <Text style={s.desc}>
        Επέλεξε τον Δήμο σου για να ψηφίζεις{"\n"}σε τοπικές αποφάσεις.
      </Text>
      <View style={s.pickerWrap}>
        <Picker
          selectedValue={selPeriferia}
          onValueChange={v => { setSelPeriferia(v); setSelDimos(null); }}
          style={s.picker}
        >
          <Picker.Item label="— Περιφέρεια —" value={null} />
          {periferias.map(p => <Picker.Item key={p.id} label={p.name_el} value={p.id} />)}
        </Picker>
      </View>
      {selPeriferia && dimoi.length > 0 && (
        <View style={s.pickerWrap}>
          <Picker selectedValue={selDimos} onValueChange={setSelDimos} style={s.picker}>
            <Picker.Item label="— Δήμος —" value={null} />
            {dimoi.map(d => <Picker.Item key={d.id} label={d.name_el} value={d.id} />)}
          </Picker>
        </View>
      )}
      <Text style={s.hint}>Προαιρετικό — μπορείτε να αλλάξετε αργότερα στο Προφίλ</Text>
      <TouchableOpacity style={s.ctaBtn} onPress={next}>
        <Text style={s.ctaBtnText}>{selDimos ? "Επόμενο →" : "Θα το ορίσω αργότερα →"}</Text>
      </TouchableOpacity>
    </View>,

    // Screen 5: Ready
    <View key="5" style={[s.screen, { backgroundColor: "#f0fdf4" }]}>
      <Text style={s.icon}>✅</Text>
      <Text style={s.title}>Είστε έτοιμοι!</Text>
      <Text style={s.desc}>
        Επαληθεύστε τον αριθμό σας για να ψηφίσετε,{"\n"}
        ή εξερευνήστε τα νομοσχέδια πρώτα.
      </Text>
      <TouchableOpacity style={s.ctaBtn} onPress={goVerify}>
        <Text style={s.ctaBtnText}>📱 Επαλήθευση τηλεφώνου</Text>
      </TouchableOpacity>
      <TouchableOpacity style={s.secondaryBtn} onPress={complete}>
        <Text style={s.secondaryBtnText}>Περιήγηση χωρίς λογαριασμό →</Text>
      </TouchableOpacity>
    </View>,
  ];

  return (
    <View style={s.container}>
      <FlatList
        ref={flatRef}
        data={screens}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        scrollEnabled={false}
        keyExtractor={(_, i) => String(i)}
        renderItem={({ item }) => item}
        onMomentumScrollEnd={e => {
          setCurrent(Math.round(e.nativeEvent.contentOffset.x / width));
        }}
      />

      {/* Progress dots */}
      <View style={s.dots}>
        {[0, 1, 2, 3, 4].map(i => (
          <View key={i} style={[s.dot, current === i && s.dotActive]} />
        ))}
      </View>

      {/* Skip */}
      {current < 4 && (
        <TouchableOpacity style={s.skipBtn} onPress={skip}>
          <Text style={s.skipText}>Παράλειψη</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  screen: { width, flex: 1, justifyContent: "center", alignItems: "center", paddingHorizontal: 32 },
  logo: { width: 100, height: 100, borderRadius: 20, marginBottom: 16 },
  icon: { fontSize: 56, marginBottom: 16 },
  title: { fontSize: 28, fontWeight: "900", color: colors.text, textAlign: "center", marginBottom: 8 },
  subtitle: { fontSize: 14, color: colors.textSecondary, marginBottom: 16 },
  tagline: { fontSize: 22, fontWeight: "700", color: colors.primary, marginBottom: 12 },
  desc: { fontSize: 16, color: colors.textSecondary, textAlign: "center", lineHeight: 24, marginBottom: 24 },
  bullets: { alignSelf: "stretch", marginBottom: 24 },
  bullet: { fontSize: 14, color: colors.text, lineHeight: 28, paddingLeft: 8 },
  disclaimer: { backgroundColor: "#fefce8", borderRadius: 12, padding: 14, marginBottom: 24 },
  disclaimerText: { fontSize: 12, color: "#92400e", lineHeight: 18, textAlign: "center" },
  ctaBtn: { backgroundColor: colors.primary, paddingHorizontal: 32, paddingVertical: 16, borderRadius: 16, marginBottom: 12 },
  ctaBtnText: { color: "#fff", fontSize: 16, fontWeight: "800" },
  secondaryBtn: { paddingHorizontal: 16, paddingVertical: 12 },
  secondaryBtnText: { color: colors.primary, fontSize: 14, fontWeight: "600" },
  pickerWrap: { alignSelf: "stretch", backgroundColor: colors.surface, borderRadius: 12, borderWidth: 1, borderColor: colors.border, marginBottom: 12, overflow: "hidden" },
  picker: { height: 50 },
  hint: { fontSize: 12, color: colors.textTertiary, marginBottom: 20, textAlign: "center" },
  dots: { flexDirection: "row", justifyContent: "center", position: "absolute", bottom: 20, left: 0, right: 0 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.border, marginHorizontal: 4 },
  dotActive: { backgroundColor: colors.primary, width: 24 },
  skipBtn: { position: "absolute", top: 56, right: 24 },
  skipText: { color: colors.textTertiary, fontSize: 14, fontWeight: "600" },
});
