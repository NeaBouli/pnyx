/**
 * ImportAccountScreen — Deep-Link Handler für ekklesia://import-account
 * Importiert Admin-generiertes Keypair in SecureStore.
 * Nur für Test/Dev Geräte.
 */
import React, { useState, useEffect } from "react";
import { View, Text, StyleSheet, ActivityIndicator } from "react-native";
import * as SecureStore from "expo-secure-store";
import type { StackScreenProps } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
import { colors } from "../theme";

type Props = StackScreenProps<RootStackParams, "ImportAccount">;

export default function ImportAccountScreen({ route, navigation }: Props) {
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("Εισαγωγή λογαριασμού...");

  useEffect(() => {
    importAccount();
  }, []);

  async function importAccount() {
    try {
      const params = route.params as {
        key?: string; nullifier?: string; pubkey?: string;
      } | undefined;

      const privateKey = params?.key;
      const nullifier = params?.nullifier;
      const pubkey = params?.pubkey;

      if (!privateKey || !nullifier) {
        setStatus("error");
        setMessage("Μη έγκυρος σύνδεσμος — λείπουν παράμετροι.");
        return;
      }

      // Store in SecureStore (same keys as crypto-native.ts)
      await SecureStore.setItemAsync("ekklesia_private_key", privateKey);
      await SecureStore.setItemAsync("ekklesia_nullifier", nullifier);
      if (pubkey) {
        await SecureStore.setItemAsync("ekklesia_public_key", pubkey);
      }
      await SecureStore.setItemAsync("onboarding_completed", "true");
      await SecureStore.setItemAsync("user_profile_completed", "true");

      setStatus("success");
      setMessage("Λογαριασμός εισήχθη επιτυχώς!");

      // Navigate to main screen after 2s
      setTimeout(() => navigation.navigate("Tabs"), 2000);
    } catch (e: any) {
      setStatus("error");
      setMessage(e.message || "Σφάλμα εισαγωγής");
    }
  }

  return (
    <View style={s.container}>
      {status === "loading" && (
        <>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={s.text}>{message}</Text>
        </>
      )}
      {status === "success" && (
        <>
          <Text style={s.icon}>✅</Text>
          <Text style={s.title}>Επιτυχία</Text>
          <Text style={s.text}>{message}</Text>
        </>
      )}
      {status === "error" && (
        <>
          <Text style={s.icon}>❌</Text>
          <Text style={s.title}>Σφάλμα</Text>
          <Text style={s.text}>{message}</Text>
        </>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.background, padding: 32 },
  icon: { fontSize: 64, marginBottom: 16 },
  title: { fontSize: 24, fontWeight: "900", color: colors.text, marginBottom: 8 },
  text: { fontSize: 16, color: colors.textSecondary, textAlign: "center", marginTop: 12 },
});
