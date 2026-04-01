import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createStackNavigator } from "@react-navigation/stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { Text } from "react-native";

import HomeScreen from "../screens/HomeScreen";
import VerifyScreen from "../screens/VerifyScreen";
import BillsScreen from "../screens/BillsScreen";
import VoteScreen from "../screens/VoteScreen";
import ResultScreen from "../screens/ResultScreen";
import TrendingScreen from "../screens/TrendingScreen";
import MPScreen from "../screens/MPScreen";

export type RootStackParams = {
  Tabs: undefined;
  Verify: undefined;
  Vote: { billId: string; billTitle: string };
  Result: { billId: string };
};

export type TabParams = {
  Home: undefined;
  Bills: undefined;
  Trending: undefined;
  MP: undefined;
};

const Stack = createStackNavigator<RootStackParams>();
const Tab = createBottomTabNavigator<TabParams>();

const TAB_ICONS: Record<string, string> = {
  Home: "🏠", Bills: "🏛️", Trending: "🔥", MP: "📊",
};

function TabNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: "#2563eb" },
        headerTintColor: "#ffffff",
        headerTitleStyle: { fontWeight: "900" },
        tabBarStyle: { backgroundColor: "#0f172a", borderTopColor: "#1e293b" },
        tabBarActiveTintColor: "#2563eb",
        tabBarInactiveTintColor: "#64748b",
        tabBarLabel: ({ color }: { color: string }) => (
          <Text style={{ color, fontSize: 10, fontWeight: "700" }}>{route.name === "Home" ? "εκκλησία" : route.name === "Bills" ? "Ψηφοφορίες" : route.name === "Trending" ? "Trending" : "Κόμματα"}</Text>
        ),
        tabBarIcon: () => (
          <Text style={{ fontSize: 18 }}>{TAB_ICONS[route.name] || "●"}</Text>
        ),
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} options={{ title: "εκκλησία" }} />
      <Tab.Screen name="Bills" component={BillsScreen} options={{ title: "Ψηφοφορίες" }} />
      <Tab.Screen name="Trending" component={TrendingScreen} options={{ title: "Trending" }} />
      <Tab.Screen name="MP" component={MPScreen} options={{ title: "Κόμματα" }} />
    </Tab.Navigator>
  );
}

export default function Navigation() {
  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        <Stack.Screen name="Tabs" component={TabNavigator} />
        <Stack.Screen name="Verify" component={VerifyScreen} options={{ headerShown: true, headerStyle: { backgroundColor: "#2563eb" }, headerTintColor: "#fff", title: "Επαλήθευση" }} />
        <Stack.Screen name="Vote" component={VoteScreen} options={{ headerShown: true, headerStyle: { backgroundColor: "#2563eb" }, headerTintColor: "#fff", title: "Ψηφίστε" }} />
        <Stack.Screen name="Result" component={ResultScreen} options={{ headerShown: true, headerStyle: { backgroundColor: "#2563eb" }, headerTintColor: "#fff", title: "Αποτελέσματα" }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
