/**
 * Navigation — Stack Navigator
 * Αρχική → Επαλήθευση → Νομοσχέδια → Ψηφοφορία → Αποτελέσματα
 */
import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import HomeScreen from "../screens/HomeScreen";
import VerifyScreen from "../screens/VerifyScreen";
import BillsScreen from "../screens/BillsScreen";
import VoteScreen from "../screens/VoteScreen";
import ResultScreen from "../screens/ResultScreen";

export type RootStackParamList = {
  Home: undefined;
  Verify: undefined;
  Bills: undefined;
  Vote: { billId: string; titleEl: string };
  Result: { billId: string; titleEl: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function RootNavigator() {
  return (
    <NavigationContainer>
      <Stack.Navigator
        initialRouteName="Home"
        screenOptions={{
          headerStyle: { backgroundColor: "#1a237e" },
          headerTintColor: "#fff",
          headerTitleStyle: { fontWeight: "bold" },
        }}
      >
        <Stack.Screen
          name="Home"
          component={HomeScreen}
          options={{ title: "Εκκλησία" }}
        />
        <Stack.Screen
          name="Verify"
          component={VerifyScreen}
          options={{ title: "Επαλήθευση" }}
        />
        <Stack.Screen
          name="Bills"
          component={BillsScreen}
          options={{ title: "Νομοσχέδια" }}
        />
        <Stack.Screen
          name="Vote"
          component={VoteScreen}
          options={({ route }) => ({ title: route.params.titleEl })}
        />
        <Stack.Screen
          name="Result"
          component={ResultScreen}
          options={{ title: "Αποτελέσματα" }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
