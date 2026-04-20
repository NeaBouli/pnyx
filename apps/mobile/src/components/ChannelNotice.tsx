import React, { useState, useEffect } from "react";
import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Image,
} from "react-native";
import * as SecureStore from "expo-secure-store";
import Constants from "expo-constants";

const NOTICE_KEY = "channel_notice_shown";

const MESSAGES = {
  direct: {
    body: "Εγκαταστήσατε την εκκλησία απευθείας από το ekklesia.gr.\n\nℹ️ Αν εγκαταστήσετε την έκδοση Google Play στο μέλλον, θα χρειαστεί να απεγκαταστήσετε αυτή την έκδοση πρώτα και να επαληθευτείτε ξανά.",
  },
  play: {
    body: "Εγκαταστήσατε την εκκλησία μέσω Google Play.\n\nℹ️ Αν μεταβείτε στην άμεση λήψη από ekklesia.gr, θα χρειαστεί να απεγκαταστήσετε αυτή την έκδοση πρώτα και να επαληθευτείτε ξανά.",
  },
} as const;

export function ChannelNotice(): React.JSX.Element | null {
  const [visible, setVisible] = useState(false);
  const [checked, setChecked] = useState(false);

  const channel =
    (Constants.expoConfig?.extra?.distributionChannel as string) ?? "direct";

  useEffect(() => {
    SecureStore.getItemAsync(NOTICE_KEY).then((val) => {
      if (!val) setVisible(true);
    });
  }, []);

  const dismiss = async () => {
    await SecureStore.setItemAsync(NOTICE_KEY, "1");
    setVisible(false);
  };

  if (!visible) return null;

  const msg = MESSAGES[channel as keyof typeof MESSAGES] ?? MESSAGES.direct;

  return (
    <Modal visible={visible} animationType="fade" transparent>
      <View style={styles.overlay}>
        <View style={styles.card}>
          <Image
            source={require("../../assets/pnx.png")}
            style={styles.logo}
            resizeMode="contain"
          />
          <Text style={styles.title}>Σημαντική Πληροφορία</Text>
          <Text style={styles.body}>{msg.body}</Text>

          <TouchableOpacity
            style={styles.checkRow}
            onPress={() => setChecked(!checked)}
            activeOpacity={0.7}
          >
            <View style={[styles.checkbox, checked && styles.checkboxChecked]}>
              {checked && <Text style={styles.checkmark}>✓</Text>}
            </View>
            <Text style={styles.checkLabel}>Το κατανοώ</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.button, !checked && styles.buttonDisabled]}
            onPress={dismiss}
            disabled={!checked}
            activeOpacity={0.7}
          >
            <Text style={styles.buttonText}>Συνέχεια →</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  card: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 24,
    width: "100%",
    maxWidth: 360,
    alignItems: "center",
  },
  logo: {
    width: 64,
    height: 64,
    marginBottom: 16,
  },
  title: {
    fontSize: 20,
    fontWeight: "700",
    color: "#1e293b",
    marginBottom: 12,
  },
  body: {
    fontSize: 14,
    color: "#475569",
    lineHeight: 22,
    textAlign: "center",
    marginBottom: 20,
  },
  checkRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 20,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 4,
    borderWidth: 2,
    borderColor: "#93c5fd",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 10,
  },
  checkboxChecked: {
    backgroundColor: "#3b82f6",
    borderColor: "#3b82f6",
  },
  checkmark: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "700",
  },
  checkLabel: {
    fontSize: 14,
    color: "#1e293b",
  },
  button: {
    backgroundColor: "#3b82f6",
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 32,
    width: "100%",
    alignItems: "center",
  },
  buttonDisabled: {
    backgroundColor: "#cbd5e1",
  },
  buttonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
});
