import { useEffect } from "react";
import { AppState } from "react-native";
import { StatusBar } from "expo-status-bar";
import Navigation from "./src/navigation";
import { clearNotificationBadge } from "./src/lib/notifications";

export default function App() {
  useEffect(() => {
    clearNotificationBadge().catch(() => {});
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") clearNotificationBadge().catch(() => {});
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
