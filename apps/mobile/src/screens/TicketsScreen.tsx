import React from "react";
import { View, StyleSheet } from "react-native";
import { WebView } from "react-native-webview";

export default function TicketsScreen() {
  return (
    <View style={s.container}>
      <WebView
        source={{ uri: "https://ekklesia.gr/tickets/" }}
        style={s.webview}
        startInLoadingState
        javaScriptEnabled
      />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f172a" },
  webview: { flex: 1 },
});
