/**
 * PolisLoginScreen — Deep-Link Handler für ekklesia://polis-login
 * Empfängt session_id + challenge aus QR-Code, signiert mit Ed25519, authentifiziert Browser-Session.
 */
import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import type { StackScreenProps } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
import { loadKeypair, loadNullifier } from "../lib/crypto-native";
import { colors } from "../theme";
import { ed25519 } from "@noble/curves/ed25519";

const API_BASE = "https://api.ekklesia.gr";

type Props = StackScreenProps<RootStackParams, "PolisLogin">;

function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return bytes;
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export default function PolisLoginScreen({ route, navigation }: Props) {
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("Υπογραφή challenge...");

  useEffect(() => {
    authenticate();
  }, []);

  async function authenticate() {
    try {
      const params = route.params as { session?: string; challenge?: string } | undefined;
      const session_id = params?.session;
      const challenge = params?.challenge;

      if (!session_id || !challenge) {
        setStatus("error");
        setMessage("Μη έγκυρος σύνδεσμος — λείπουν παράμετροι.");
        return;
      }

      // Load credentials from SecureStore
      const keypair = await loadKeypair();
      const nullifier = await loadNullifier();

      if (!keypair || !nullifier) {
        setStatus("error");
        setMessage("Δεν έχετε επαληθευτεί. Παρακαλώ επαληθεύστε πρώτα τον αριθμό σας.");
        return;
      }

      // Sign the challenge with Ed25519
      const challengeBytes = new TextEncoder().encode(challenge);
      const signatureBytes = ed25519.sign(challengeBytes, hexToBytes(keypair.privateKeyHex));
      const signatureHex = bytesToHex(signatureBytes);

      // POST to API
      const response = await fetch(`${API_BASE}/api/v1/polis/qr-auth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id,
          nullifier_hash: nullifier,
          public_key_hex: keypair.publicKeyHex,
          signature_hex: signatureHex,
        }),
      });

      if (response.ok) {
        setStatus("success");
        setMessage("Επιτυχής σύνδεση στο POLIS!");
      } else {
        const data = await response.json().catch(() => ({ detail: "Unknown error" }));
        setStatus("error");
        setMessage(data.detail || `Σφάλμα ${response.status}`);
      }
    } catch (e: any) {
      setStatus("error");
      setMessage(e.message || "Σφάλμα σύνδεσης");
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
          <Text style={s.hint}>Μπορείτε να κλείσετε αυτή την οθόνη.</Text>
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
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.background,
    padding: 32,
  },
  icon: { fontSize: 64, marginBottom: 16 },
  title: { fontSize: 24, fontWeight: "900", color: colors.text, marginBottom: 8 },
  text: { fontSize: 16, color: colors.textSecondary, textAlign: "center", marginTop: 12 },
  hint: { fontSize: 14, color: colors.textSecondary, marginTop: 24, opacity: 0.7 },
});
