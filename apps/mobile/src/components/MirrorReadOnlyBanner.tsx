import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { getApiTransportState, subscribeApiTransport, type ApiTransportState } from "../lib/api";
import { colors } from "../theme";

export function MirrorReadOnlyBanner(): React.JSX.Element | null {
  const [state, setState] = useState<ApiTransportState>(getApiTransportState());

  useEffect(() => subscribeApiTransport(setState), []);

  if (state.mode !== "mirror_readonly") return null;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Μόνο ανάγνωση</Text>
      <Text style={styles.body}>
        Ο κύριος server δεν είναι διαθέσιμος. Βλέπετε προσωρινά το mirror· η ψήφος δεν είναι διαθέσιμη.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.warningBg,
    borderBottomColor: "#facc15",
    borderBottomWidth: 1,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  title: {
    color: "#92400e",
    fontSize: 13,
    fontWeight: "900",
  },
  body: {
    color: "#92400e",
    fontSize: 12,
    fontWeight: "600",
    lineHeight: 17,
    marginTop: 2,
  },
});
