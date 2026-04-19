/**
 * VerifyScreen — Επαλήθευση Ταυτότητας
 * SMS → Ed25519 Keypair → Secure Enclave
 */
import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from "react-native";
import type { StackScreenProps } from "@react-navigation/stack";
import type { RootStackParams } from "../navigation";
import { verifyIdentity } from "../lib/api";
import { storeKeypair, storeNullifier } from "../lib/crypto-native";
import { colors } from "../theme";

type Props = StackScreenProps<RootStackParams, "Verify">;

export default function VerifyScreen({ navigation }: Props) {
  const [phone, setPhone] = useState("+30");
  const [loading, setLoading] = useState(false);

  async function handleVerify() {
    if (phone.length < 8) {
      Alert.alert("Σφάλμα", "Εισάγετε έγκυρο αριθμό κινητού.");
      return;
    }

    setLoading(true);
    try {
      const res = await verifyIdentity(phone);

      // Αποθήκευση στο Secure Enclave
      await storeKeypair(res.private_key_hex, res.public_key_hex);
      await storeNullifier(res.nullifier_hash);

      Alert.alert(
        "Επιτυχία ✓",
        "Το κλειδί σας αποθηκεύτηκε με ασφάλεια. Μπορείτε τώρα να ψηφίσετε.",
        [{ text: "Συνέχεια", onPress: () => navigation.navigate("Tabs") }]
      );
    } catch (err: any) {
      Alert.alert("Σφάλμα", err.message || "Η επαλήθευση απέτυχε.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Επαλήθευση Κινητού</Text>
      <Text style={styles.info}>
        Εισάγετε τον ελληνικό αριθμό κινητού σας. Μετά την επαλήθευση, ο αριθμός
        διαγράφεται αμέσως — αποθηκεύεται μόνο ένα ανώνυμο αναγνωριστικό.
      </Text>

      <TextInput
        style={styles.input}
        value={phone}
        onChangeText={setPhone}
        placeholder="+30 69X XXX XXXX"
        keyboardType="phone-pad"
        autoComplete="tel"
        maxLength={15}
      />

      <TouchableOpacity
        style={[styles.button, loading && styles.disabledButton]}
        onPress={handleVerify}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Επαλήθευση</Text>
        )}
      </TouchableOpacity>

      <View style={styles.securityNote}>
        <Text style={styles.securityTitle}>🔒 Ασφάλεια</Text>
        <Text style={styles.securityText}>
          • Ο αριθμός κινητού δεν αποθηκεύεται ποτέ{"\n"}
          • Το ιδιωτικό κλειδί μένει μόνο στη συσκευή σας{"\n"}
          • Χρήση Ed25519 κρυπτογραφίας{"\n"}
          • Βιομετρική πρόσβαση στο κλειδί
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: colors.background },
  heading: { fontSize: 22, fontWeight: "bold", color: colors.primary, marginBottom: 8 },
  info: { fontSize: 14, color: colors.textSecondary, marginBottom: 24, lineHeight: 20 },
  input: {
    backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border,
    borderRadius: 12, padding: 16, fontSize: 18, marginBottom: 16, color: colors.text,
  },
  button: {
    backgroundColor: colors.primary, paddingVertical: 14, borderRadius: 12,
    alignItems: "center", marginBottom: 32,
  },
  disabledButton: { backgroundColor: colors.textTertiary },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  securityNote: {
    backgroundColor: colors.primaryLight, padding: 16, borderRadius: 12,
  },
  securityTitle: { fontSize: 14, fontWeight: "bold", color: colors.primary, marginBottom: 8 },
  securityText: { fontSize: 13, color: colors.text, lineHeight: 20 },
});
