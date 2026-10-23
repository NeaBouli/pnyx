import React from "react";
import { Linking, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import type { Bill } from "../lib/api";
import { colors } from "../theme";

export type AttributionBill = Pick<Bill,
  "source" | "source_last_success" | "created_at" | "official_source_url" | "parliament_url">;

export default function ParliamentAttribution({ bill, locale = "el" }: { bill: AttributionBill; locale?: string }) {
  if (bill.source !== "PARLIAMENT") return null;
  const el = locale === "el";
  // The API's legacy naive timestamps are UTC, irrespective of the reader's timezone.
  const date = [bill.source_last_success, bill.created_at].flatMap((value) => {
    if (!value) return [];
    const parsed = new Date(value.includes("T") && !/(Z|[+-]\d{2}:?\d{2})$/i.test(value) ? `${value}Z` : value);
    return Number.isFinite(parsed.getTime()) ? [parsed] : [];
  })[0];
  const url = bill.official_source_url || bill.parliament_url;
  return (
    <View style={styles.container}>
      <Text style={styles.text}>{el ? "Αναδημοσίευση από τη διαδικτυακή πύλη της Βουλής των Ελλήνων"
        : "Republished from the website of the Hellenic Parliament"}</Text>
      <Text style={styles.text}>
        {el ? "Ημερομηνία: " : "Date: "}
        {date ? date.toLocaleDateString("en-GB", {
          timeZone: "Europe/Athens", day: "2-digit", month: "2-digit", year: "numeric",
        }) : (el ? "Μη διαθέσιμη" : "Unavailable")}
      </Text>
      {url && /^https?:\/\//i.test(url) && <TouchableOpacity accessibilityRole="link"
        accessibilityHint={el ? "Ανοίγει στο πρόγραμμα περιήγησης" : "Opens in your browser"}
        onPress={(event) => { event.stopPropagation(); void Linking.openURL(url); }} style={styles.linkTarget}>
        <Text style={styles.link}>{el ? "Πρωτότυπο" : "Original"}</Text>
      </TouchableOpacity>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginVertical: 8 },
  text: { color: colors.textSecondary, fontSize: 12, lineHeight: 18 },
  linkTarget: { alignSelf: "flex-start", minHeight: 44, justifyContent: "center" },
  link: { color: colors.primary, fontSize: 12, textDecorationLine: "underline" },
});
