import React, { useState, useEffect } from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createStackNavigator } from "@react-navigation/stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { Text, ActivityIndicator, View, useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as SecureStore from "expo-secure-store";
import { colors } from "../theme";
import { ChannelNotice } from "../components/ChannelNotice";
import { MirrorReadOnlyBanner } from "../components/MirrorReadOnlyBanner";
import { UpdateBanner } from "../components/UpdateBanner";

import OnboardingScreen from "../screens/OnboardingScreen";
import HomeScreen from "../screens/HomeScreen";
import VerifyScreen from "../screens/VerifyScreen";
import BillsScreen from "../screens/BillsScreen";
import VoteScreen from "../screens/VoteScreen";
import ResultScreen from "../screens/ResultScreen";
import TrendingScreen from "../screens/TrendingScreen";
import MPScreen from "../screens/MPScreen";
import TicketsScreen from "../screens/TicketsScreen";
import ProfileScreen from "../screens/ProfileScreen";
import NotificationSettingsScreen from "../screens/NotificationSettingsScreen";
import CompassScreen from "../screens/CompassScreen";
import PolisLoginScreen from "../screens/PolisLoginScreen";
import ImportAccountScreen from "../screens/ImportAccountScreen";
import { linking } from "./linking";
import { getTabBarMetrics, TAB_BAR_MAX_FONT_SIZE_MULTIPLIER } from "./tab-bar-layout";
import PolitikoiScreen from "../screens/PolitikoiScreen";
import EvaluatePoliticianScreen from "../screens/EvaluatePoliticianScreen";
import ZkSemaphoreScreen from "../screens/ZkSemaphoreScreen";
import DiavgeiaResultsScreen from "../screens/DiavgeiaResultsScreen";

export type RootStackParams = {
  Onboarding: undefined;
  Tabs: undefined;
  Verify: undefined;
  Profile: undefined;
  NotificationSettings: undefined;
  Compass: undefined;
  Vote: { billId: string; billTitle?: string };
  Result: { billId: string; billTitle?: string; fromVote?: boolean };
  Politikoi: undefined;
  EvaluatePolitician: { adaNumber: string; orgLabel: string };
  PolisLogin: { session?: string; challenge?: string; purpose?: string; bill_id?: string };
  ImportAccount: undefined;
  ZkSemaphore: undefined;
  DiavgeiaResults: undefined;
};

export type TabParams = {
  Home: undefined;
  Bills: undefined;
  Trending: undefined;
  MP: undefined;
  Tickets: undefined;
};

const Stack = createStackNavigator<RootStackParams>();
const Tab = createBottomTabNavigator<TabParams>();

const TAB_ICONS: Record<string, string> = {
  Home: "🏠", Bills: "🏛️", Trending: "🔥", MP: "📊", Tickets: "🎫",
};

function TabNavigator() {
  const { fontScale, width, height } = useWindowDimensions();
  const { bottom } = useSafeAreaInsets();
  const tabBar = getTabBarMetrics(fontScale, bottom);

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: colors.headerBg },
        headerTintColor: colors.headerText,
        headerTitleStyle: { fontWeight: "900" },
        tabBarStyle: { backgroundColor: colors.tabBarBg, borderTopColor: colors.border, height: tabBar.height },
        tabBarItemStyle: { minWidth: 48, minHeight: 48 },
        tabBarIconStyle: { width: tabBar.iconWidth, height: tabBar.iconHeight },
        tabBarLabelPosition: width > height ? "beside-icon" : "below-icon",
        tabBarAccessibilityLabel: route.name === "Home" ? "εκκλησία" : route.name === "Bills" ? "Ψηφοφορίες" : route.name === "Trending" ? "Trending" : route.name === "Tickets" ? "POLIS" : "Κόμματα",
        tabBarActiveTintColor: colors.tabBarActive,
        tabBarInactiveTintColor: colors.tabBarInactive,
        // GH-298: cap scaling locally and let the bar grow with the same scale.
        tabBarLabel: ({ color, position }) => (
          <Text
            maxFontSizeMultiplier={TAB_BAR_MAX_FONT_SIZE_MULTIPLIER}
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.75}
            ellipsizeMode="tail"
            style={{ color, fontSize: 10, lineHeight: 14, fontWeight: "700", flexShrink: 1, maxWidth: "100%", textAlign: "center", marginStart: position === "beside-icon" ? 5 : 0 }}
          >
            {route.name === "Home" ? "εκκλησία" : route.name === "Bills" ? "Ψ/φορία" : route.name === "Trending" ? "Trending" : route.name === "Tickets" ? "POLIS" : "Κόμματα"}
          </Text>
        ),
        // The navigator's icon wrapper grows too, keeping scaled emoji inside it.
        tabBarIcon: ({ size }: { size: number }) => (
          <Text maxFontSizeMultiplier={TAB_BAR_MAX_FONT_SIZE_MULTIPLIER} numberOfLines={1} style={{ fontSize: Math.round(Math.min(size, 28) * 0.8), lineHeight: Math.min(size, 28), textAlign: "center" }}>
            {TAB_ICONS[route.name] || "●"}
          </Text>
        ),
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} options={{ title: "εκκλησία" }} />
      <Tab.Screen name="Bills" component={BillsScreen} options={{ title: "Ψηφοφορίες" }} />
      <Tab.Screen name="Trending" component={TrendingScreen} options={{ title: "Trending" }} />
      <Tab.Screen name="MP" component={MPScreen} options={{ title: "Κόμματα" }} />
      <Tab.Screen name="Tickets" component={TicketsScreen} options={{ title: "POLIS" }} />
    </Tab.Navigator>
  );
}

export default function Navigation() {
  const [loading, setLoading] = useState(true);
  const [onboarded, setOnboarded] = useState(true);

  useEffect(() => {
    SecureStore.getItemAsync("onboarding_completed").then(v => {
      setOnboarded(v === "true");
      setLoading(false);
    });
  }, []);

  if (loading) return <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.background }}><ActivityIndicator color={colors.primary} /></View>;

  return (
    <NavigationContainer linking={linking}>
      <ChannelNotice />
      <UpdateBanner />
      <MirrorReadOnlyBanner />
      <Stack.Navigator screenOptions={{ headerShown: false }} initialRouteName={onboarded ? "Tabs" : "Onboarding"}>
        <Stack.Screen name="Onboarding" component={OnboardingScreen} />
        <Stack.Screen name="Tabs" component={TabNavigator} />
        <Stack.Screen name="Verify" component={VerifyScreen} options={{ headerShown: true, headerStyle: { backgroundColor: colors.headerBg }, headerTintColor: colors.headerText, title: "Επαλήθευση" }} />
        <Stack.Screen name="Profile" component={ProfileScreen} options={{ headerShown: true, headerStyle: { backgroundColor: colors.headerBg }, headerTintColor: colors.headerText, title: "Προφίλ" }} />
        <Stack.Screen name="NotificationSettings" component={NotificationSettingsScreen} options={{ headerShown: true, headerStyle: { backgroundColor: colors.headerBg }, headerTintColor: colors.headerText, title: "Ειδοποιήσεις" }} />
        <Stack.Screen name="Compass" component={CompassScreen} options={{ headerShown: true, headerStyle: { backgroundColor: colors.headerBg }, headerTintColor: colors.headerText, title: "Πολιτική Πυξίδα" }} />
        <Stack.Screen name="Vote" component={VoteScreen} options={{ headerShown: true, headerStyle: { backgroundColor: colors.headerBg }, headerTintColor: colors.headerText, title: "Ψηφίστε" }} />
        <Stack.Screen name="Result" component={ResultScreen} options={{ headerShown: true, headerStyle: { backgroundColor: colors.headerBg }, headerTintColor: colors.headerText, title: "Αποτελέσματα" }} />
        <Stack.Screen name="Politikoi" component={PolitikoiScreen} options={{ headerShown: true, headerStyle: { backgroundColor: colors.headerBg }, headerTintColor: colors.headerText, title: "Πολιτικοί" }} />
        <Stack.Screen name="EvaluatePolitician" component={EvaluatePoliticianScreen} options={{ headerShown: true, headerStyle: { backgroundColor: colors.headerBg }, headerTintColor: colors.headerText, title: "Αξιολόγηση" }} />
        <Stack.Screen name="PolisLogin" component={PolisLoginScreen} options={{ headerShown: true, headerStyle: { backgroundColor: colors.headerBg }, headerTintColor: colors.headerText, title: "POLIS Login" }} />
        <Stack.Screen name="ImportAccount" component={ImportAccountScreen} options={{ headerShown: true, headerStyle: { backgroundColor: colors.headerBg }, headerTintColor: colors.headerText, title: "Import Account" }} />
        <Stack.Screen name="ZkSemaphore" component={ZkSemaphoreScreen} options={{ headerShown: true, headerStyle: { backgroundColor: colors.headerBg }, headerTintColor: colors.headerText, title: "Semaphore ZK V2" }} />
        <Stack.Screen name="DiavgeiaResults" component={DiavgeiaResultsScreen} options={{ headerShown: true, headerStyle: { backgroundColor: colors.headerBg }, headerTintColor: colors.headerText, title: "Αποτελέσματα Διαύγειας" }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
