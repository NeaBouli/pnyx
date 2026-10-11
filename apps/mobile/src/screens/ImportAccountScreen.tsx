/**
 * ImportAccountScreen — imports an admin-generated test identity.
 *
 * EVA-034: reachable only from inside the app (Profile), never via deep link.
 * The pasted code is validated (format, checksum, key pair) before anything is
 * shown; the user then sees the public key fingerprint and, if an identity is
 * already stored, an explicit replacement warning, and must confirm. The code
 * is kept only in component state, cleared after validation or cancel, and is
 * never logged or persisted.
 */
import React, { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView } from "react-native";
import * as SecureStore from "expo-secure-store";
import type { StackScreenProps } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
import { importAccountCredentials, type ImportedAccountCredentials } from "../lib/import-account";
import { parseImportCode, publicKeyFingerprint } from "../lib/import-code";
import { colors } from "../theme";

type Props = StackScreenProps<RootStackParams, "ImportAccount">;

type Step =
  | { kind: "enter" }
  | { kind: "confirm"; credentials: ImportedAccountCredentials; replacesIdentity: boolean }
  | { kind: "importing" }
  | { kind: "success" }
  | { kind: "error"; message: string };

const PARSE_ERRORS: Record<string, string> = {
  "invalid-format": "Μη έγκυρος κωδικός εισαγωγής.",
  "invalid-checksum": "Ο κωδικός είναι ελλιπής ή περιέχει λάθος. Αντιγράψτε τον ξανά.",
  "key-mismatch": "Τα κλειδιά του κωδικού δεν ταιριάζουν.",
};

export default function ImportAccountScreen({ navigation }: Props) {
  const [code, setCode] = useState("");
  const [step, setStep] = useState<Step>({ kind: "enter" });

  async function validate() {
    let credentials: ImportedAccountCredentials;
    try {
      credentials = parseImportCode(code);
    } catch (e: unknown) {
      const key = e instanceof Error ? e.message : "";
      setStep({ kind: "error", message: PARSE_ERRORS[key] ?? PARSE_ERRORS["invalid-format"] });
      setCode("");
      return;
    }
    setCode("");
    let existing: string | null;
    try {
      existing = await SecureStore.getItemAsync("ekklesia_public_key");
    } catch {
      setStep({ kind: "error", message: "Δεν ήταν δυνατή η ανάγνωση της τρέχουσας ταυτότητας." });
      return;
    }
    setStep({
      kind: "confirm",
      credentials,
      replacesIdentity: !!existing && existing.toLowerCase() !== credentials.publicKey,
    });
  }

  async function confirmImport(credentials: ImportedAccountCredentials) {
    setStep({ kind: "importing" });
    try {
      await importAccountCredentials(credentials);
      setStep({ kind: "success" });
      setTimeout(() => navigation.navigate("Tabs"), 1500);
    } catch {
      setStep({ kind: "error", message: "Η εισαγωγή απέτυχε. Η προηγούμενη ταυτότητα διατηρήθηκε." });
    }
  }

  function cancel() {
    setCode("");
    setStep({ kind: "enter" });
  }

  return (
    <ScrollView contentContainerStyle={s.container} keyboardShouldPersistTaps="handled">
      <Text style={s.title}>Εισαγωγή δοκιμαστικού λογαριασμού</Text>
      <Text style={s.text}>Μόνο για δοκιμαστικές συσκευές. Επικολλήστε τον κωδικό που δημιούργησε ο διαχειριστής.</Text>

      {step.kind === "enter" && (
        <>
          <TextInput
            style={s.input}
            value={code}
            onChangeText={setCode}
            placeholder="EKKLESIA-IMPORT-V1:…"
            placeholderTextColor={colors.textSecondary}
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="off"
            importantForAutofill="no"
            spellCheck={false}
            keyboardType="visible-password"
            multiline
            accessibilityLabel="Κωδικός εισαγωγής"
          />
          <TouchableOpacity
            style={[s.button, !code.trim() && s.buttonDisabled]}
            disabled={!code.trim()}
            onPress={validate}
            accessibilityRole="button"
          >
            <Text style={s.buttonText}>Έλεγχος κωδικού</Text>
          </TouchableOpacity>
        </>
      )}

      {step.kind === "confirm" && (
        <View style={s.card}>
          <Text style={s.label}>Αποτύπωμα δημόσιου κλειδιού</Text>
          <Text style={s.fingerprint} accessibilityLabel="Αποτύπωμα δημόσιου κλειδιού">
            {publicKeyFingerprint(step.credentials.publicKey)}
          </Text>
          {step.replacesIdentity && (
            <Text style={s.warning}>
              ⚠️ Η τρέχουσα ταυτότητα αυτής της συσκευής θα αντικατασταθεί. Οι τοπικές ενδείξεις ψήφου της θα διαγραφούν.
            </Text>
          )}
          <TouchableOpacity style={s.button} onPress={() => confirmImport(step.credentials)} accessibilityRole="button">
            <Text style={s.buttonText}>Επιβεβαίωση εισαγωγής</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.secondary} onPress={cancel} accessibilityRole="button">
            <Text style={s.secondaryText}>Ακύρωση</Text>
          </TouchableOpacity>
        </View>
      )}

      {step.kind === "importing" && <Text style={s.text}>Εισαγωγή λογαριασμού...</Text>}

      {step.kind === "success" && <Text style={s.success}>✅ Ο λογαριασμός εισήχθη.</Text>}

      {step.kind === "error" && (
        <>
          <Text style={s.error}>❌ {step.message}</Text>
          <TouchableOpacity style={s.secondary} onPress={cancel} accessibilityRole="button">
            <Text style={s.secondaryText}>Δοκιμάστε ξανά</Text>
          </TouchableOpacity>
        </>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flexGrow: 1, backgroundColor: colors.background, padding: 24 },
  title: { fontSize: 20, fontWeight: "900", color: colors.text, marginBottom: 8 },
  text: { fontSize: 15, color: colors.textSecondary, marginTop: 8, marginBottom: 12 },
  input: {
    minHeight: 120, borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 12,
    color: colors.text, fontFamily: "monospace", fontSize: 13, textAlignVertical: "top",
  },
  button: { backgroundColor: colors.primary, borderRadius: 8, paddingVertical: 14, alignItems: "center", marginTop: 16 },
  buttonDisabled: { opacity: 0.4 },
  buttonText: { color: "#fff", fontWeight: "800", fontSize: 16 },
  secondary: { paddingVertical: 12, alignItems: "center", marginTop: 8 },
  secondaryText: { color: colors.primary, fontWeight: "700", fontSize: 15 },
  card: { borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 16, marginTop: 8 },
  label: { fontSize: 13, color: colors.textSecondary },
  fingerprint: { fontSize: 20, fontWeight: "800", color: colors.text, fontFamily: "monospace", marginTop: 6 },
  warning: { fontSize: 14, color: colors.text, marginTop: 12, fontWeight: "700" },
  success: { fontSize: 16, color: colors.text, marginTop: 16 },
  error: { fontSize: 15, color: colors.text, marginTop: 16 },
});
