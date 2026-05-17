import React, { useEffect, useState, useRef } from 'react';
import { View, ActivityIndicator, StyleSheet, Alert, StatusBar } from 'react-native';
import { WebView, WebViewMessageEvent } from 'react-native-webview';
import * as SecureStore from 'expo-secure-store';
import * as LocalAuthentication from 'expo-local-authentication';

const WEB_URL = 'https://ekklesia.gr/representative/';
const API_BASE = 'https://api.ekklesia.gr';

export default function App() {
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);
  const webRef = useRef<WebView>(null);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    const savedToken = await SecureStore.getItemAsync('rep_token');
    if (savedToken) {
      const hasBio = await LocalAuthentication.hasHardwareAsync();
      if (hasBio) {
        const result = await LocalAuthentication.authenticateAsync({
          promptMessage: 'Επαλήθευση εκπροσώπου',
          fallbackLabel: 'Χρήση PIN',
        });
        if (result.success) {
          setToken(savedToken);
        }
      } else {
        setToken(savedToken);
      }
    }
    setLoading(false);
  };

  const injectedJS = `
    window.REP_TOKEN = ${token ? `'${token}'` : 'null'};
    window.API_BASE = '${API_BASE}';
    window.IS_NATIVE = true;
    window.postToNative = function(type, data) {
      window.ReactNativeWebView.postMessage(JSON.stringify({type: type, data: data}));
    };
    true;
  `;

  const handleMessage = async (event: WebViewMessageEvent) => {
    try {
      const { type, data } = JSON.parse(event.nativeEvent.data);
      if (type === 'SAVE_TOKEN') {
        await SecureStore.setItemAsync('rep_token', data);
        setToken(data);
      } else if (type === 'LOGOUT') {
        await SecureStore.deleteItemAsync('rep_token');
        setToken(null);
      }
    } catch {}
  };

  if (loading) {
    return (
      <View style={s.loading}>
        <StatusBar barStyle="light-content" backgroundColor="#0f172a" />
        <ActivityIndicator size="large" color="#f59e0b" />
      </View>
    );
  }

  return (
    <View style={s.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0f172a" />
      <WebView
        ref={webRef}
        source={{ uri: WEB_URL }}
        injectedJavaScriptBeforeContentLoaded={injectedJS}
        style={s.webview}
        javaScriptEnabled={true}
        domStorageEnabled={false}
        incognito={true}
        onMessage={handleMessage}
        startInLoadingState={true}
        renderLoading={() => (
          <View style={s.loading}>
            <ActivityIndicator size="large" color="#f59e0b" />
          </View>
        )}
      />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  loading: { flex: 1, backgroundColor: '#0f172a', justifyContent: 'center', alignItems: 'center' },
  webview: { flex: 1, backgroundColor: '#0f172a' },
});
