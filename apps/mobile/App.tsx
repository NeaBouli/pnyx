import { useEffect } from "react";
import { AppState } from "react-native";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import Navigation from "./src/navigation";
import { colors } from "./src/theme";
import {
  reconcileNotificationBadge,
  refreshUnreadFromPublicBills,
} from "./src/lib/notifications";

export default function App() {
  useEffect(() => {
    // Per-event unread state persists across restarts; app start/foreground
    // only reconciles the native badge with the ledger (no blanket clear)
    // and runs the F-Droid foreground bill-feed fallback.
    const onActive = () => {
      reconcileNotificationBadge().catch(() => {});
      refreshUnreadFromPublicBills().catch(() => {});
    };
    onActive();
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") onActive();
    });
    return () => subscription.remove();
  }, []);

  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <SafeAreaView edges={["top"]} style={{ flex: 1, backgroundColor: colors.headerBg }}>
        {/* Navigation insets are relative to the already-safe content frame. */}
        <SafeAreaProvider>
          <Navigation />
        </SafeAreaProvider>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}
