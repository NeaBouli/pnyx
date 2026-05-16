import React, { useState, useEffect, useRef } from "react";
import { Text, TouchableOpacity, StyleSheet, Linking, Animated } from "react-native";
import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";
import { colors } from "../theme";

const API = process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr";
const CHECK_INTERVAL_MS = 30 * 60 * 1000; // 30 min

export function UpdateBanner(): React.JSX.Element | null {
  const [update, setUpdate] = useState<{ version: string; url: string } | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const slideAnim = useRef(new Animated.Value(-40)).current;

  useEffect(() => {
    SecureStore.getItemAsync("push_system_update").then(v => {
      setEnabled(v !== "false"); // default true
    });
  }, []);

  useEffect(() => {
    if (enabled === false) return;
    if (enabled === null) return; // not yet loaded

    const check = async () => {
      try {
        const currentVC = Constants.expoConfig?.android?.versionCode ?? 0;
        const res = await fetch(`${API}/api/v1/app/version`);
        const data = await res.json();
        if (data.latest_version_code > currentVC) {
          setUpdate({
            version: data.latest_version,
            url: data.direct_apk_url || data.playstore_url || "https://ekklesia.gr/download/",
          });
        }
      } catch { /* silent */ }
    };

    check();
    const interval = setInterval(check, CHECK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [enabled]);

  useEffect(() => {
    if (update && !dismissed) {
      Animated.spring(slideAnim, { toValue: 0, useNativeDriver: true }).start();
    }
  }, [update, dismissed, slideAnim]);

  if (!update || dismissed || enabled === false) return null;

  return (
    <Animated.View style={[s.container, { transform: [{ translateY: slideAnim }] }]}>
      <TouchableOpacity style={s.inner} onPress={() => { try { Linking.openURL(update.url); } catch {} }} activeOpacity={0.8}>
        <Text style={s.text}>
          v{update.version} διαθέσιμη
        </Text>
        <Text style={s.link}>Ενημέρωση →</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={() => setDismissed(true)} hitSlop={8} style={s.close}>
        <Text style={s.closeText}>✕</Text>
      </TouchableOpacity>
    </Animated.View>
  );
}

const s = StyleSheet.create({
  container: {
    backgroundColor: colors.primary,
    paddingHorizontal: 16,
    paddingVertical: 6,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  inner: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  text: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "600",
  },
  link: {
    color: "#bfdbfe",
    fontSize: 12,
    fontWeight: "700",
  },
  close: {
    paddingLeft: 12,
  },
  closeText: {
    color: "#93c5fd",
    fontSize: 14,
    fontWeight: "700",
  },
});
