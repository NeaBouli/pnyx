import { useEffect } from "react";
import { AppState } from "react-native";
import { StatusBar } from "expo-status-bar";
import Navigation from "./src/navigation";
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
    <>
      <StatusBar style="light" />
      <Navigation />
    </>
  );
}
