import React, { useEffect, useState, useCallback } from "react";
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator } from "react-native";
import { colors } from "../theme";
import { CompassEngine } from "../../../../packages/compass/src/engine";
import { QUESTIONS } from "../../../../packages/compass/src/questions";
import { PARTIES } from "../../../../packages/compass/src/parties";
import type { Answer, CompassResult, LikertValue } from "../../../../packages/compass/src/types";
import { saveCompass, getCompass } from "../lib/compassStore";

const engine = new CompassEngine();

const LIKERT_OPTIONS: { label: string; value: LikertValue }[] = [
  { label: "Διαφωνώ\nαπόλυτα", value: -2 },
  { label: "Διαφωνώ", value: -1 },
  { label: "Ουδέτερο", value: 0 },
  { label: "Συμφωνώ", value: 1 },
  { label: "Συμφωνώ\nαπόλυτα", value: 2 },
];

const QUADRANT_LABELS: Record<string, string> = {
  libertarian_left: "Ελευθεριακή Αριστερά",
  libertarian_right: "Ελευθεριακή Δεξιά",
  authoritarian_left: "Αυταρχική Αριστερά",
  authoritarian_right: "Αυταρχική Δεξιά",
};

export default function CompassScreen() {
  const [loading, setLoading] = useState(true);
  const [result, setResult] = useState<CompassResult | null>(null);
  const [answers, setAnswers] = useState<Answer[]>([]);
  const [currentQ, setCurrentQ] = useState(0);
  const [selected, setSelected] = useState<LikertValue | null>(null);
  const [mode, setMode] = useState<"loading" | "quiz" | "result">("loading");

  useEffect(() => {
    getCompass().then(data => {
      if (data.result) { setResult(data.result); setAnswers(data.answers); setMode("result"); }
      else setMode("quiz");
      setLoading(false);
    });
  }, []);

  const answer = useCallback((value: LikertValue) => {
    setSelected(value);
    const q = QUESTIONS[currentQ];
    const newAnswers = [...answers.filter(a => a.questionId !== q.id), { questionId: q.id, value, timestamp: Date.now() }];
    setAnswers(newAnswers);
    setTimeout(() => {
      if (currentQ < QUESTIONS.length - 1) { setCurrentQ(prev => prev + 1); setSelected(null); }
      else {
        const r = engine.compute(newAnswers);
        setResult(r);
        saveCompass(r, newAnswers);
        setMode("result");
      }
    }, 400);
  }, [currentQ, answers]);

  const restart = () => { setAnswers([]); setCurrentQ(0); setSelected(null); setMode("quiz"); };

  if (loading) return <View style={s.center}><ActivityIndicator color={colors.primary} /></View>;

  // ── QUIZ MODE ──
  if (mode === "quiz") {
    const q = QUESTIONS[currentQ];
    return (
      <View style={s.container}>
        <View style={s.progressBar}><View style={[s.progressFill, { width: `${((currentQ + 1) / QUESTIONS.length) * 100}%` }]} /></View>
        <Text style={s.progressText}>{currentQ + 1} / {QUESTIONS.length}</Text>
        <View style={s.questionCard}>
          <Text style={s.questionText}>{q.text}</Text>
        </View>
        <View style={s.optionsRow}>
          {LIKERT_OPTIONS.map(opt => (
            <TouchableOpacity key={opt.value} style={[s.optionBtn, selected === opt.value && s.optionSelected]} onPress={() => answer(opt.value)}>
              <Text style={[s.optionText, selected === opt.value && s.optionTextSelected]}>{opt.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
        {currentQ > 0 && (
          <TouchableOpacity style={s.backBtn} onPress={() => { setCurrentQ(prev => prev - 1); setSelected(null); }}>
            <Text style={s.backBtnText}>← Προηγούμενο</Text>
          </TouchableOpacity>
        )}
      </View>
    );
  }

  // ── RESULT MODE ──
  if (!result) return null;

  const descEcon = result.economic < -5 ? "Έντονα αριστερός/ή" : result.economic < 0 ? "Μετρίως αριστερός/ή" : result.economic > 5 ? "Έντονα δεξιός/ά" : result.economic > 0 ? "Μετρίως δεξιός/ά" : "Κεντρώος/α";
  const descSoc = result.social < -5 ? "έντονα ελευθεριακός/ή" : result.social < 0 ? "μετρίως ελευθεριακός/ή" : result.social > 5 ? "έντονα αυταρχικός/ή" : result.social > 0 ? "μετρίως αυταρχικός/ή" : "ισορροπημένος/η";

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      <Text style={s.resultTitle}>Η Πολιτική Σας Πυξίδα</Text>
      <Text style={s.quadrantLabel}>{QUADRANT_LABELS[result.quadrant]}</Text>

      {/* Simple 2D grid visualization */}
      <View style={s.compassGrid}>
        <Text style={s.axisLabelTop}>Αυταρχικό ↑</Text>
        <View style={s.compassInner}>
          <Text style={s.axisLabelLeft}>Αριστερά</Text>
          <View style={s.compassBox}>
            {/* Quadrant backgrounds */}
            <View style={[s.quadrant, { top: 0, left: 0, backgroundColor: "#fef2f2" }]} />
            <View style={[s.quadrant, { top: 0, right: 0, backgroundColor: "#fefce8" }]} />
            <View style={[s.quadrant, { bottom: 0, left: 0, backgroundColor: "#eff6ff" }]} />
            <View style={[s.quadrant, { bottom: 0, right: 0, backgroundColor: "#f0fdf4" }]} />
            {/* Axes */}
            <View style={s.axisH} /><View style={s.axisV} />
            {/* Party dots */}
            {PARTIES.map(p => (
              <View key={p.name} style={[s.partyDot, { left: `${(p.x + 10) / 20 * 100}%`, bottom: `${(-p.y + 10) / 20 * 100}%`, backgroundColor: p.color }]}>
                <Text style={s.partyLabel}>{p.name}</Text>
              </View>
            ))}
            {/* User dot */}
            <View style={[s.userDot, { left: `${(result.economic + 10) / 20 * 100}%`, bottom: `${(-result.social + 10) / 20 * 100}%` }]} />
          </View>
          <Text style={s.axisLabelRight}>Δεξιά</Text>
        </View>
        <Text style={s.axisLabelBottom}>↓ Ελευθεριακό</Text>
      </View>

      <Text style={s.description}>{descEcon} οικονομικά, {descSoc} κοινωνικά.</Text>

      {/* Party matches */}
      <Text style={s.sectionTitle}>Εγγύτητα Κομμάτων</Text>
      {result.partyMatches.slice(0, 5).map(p => (
        <View key={p.name} style={s.matchRow}>
          <Text style={s.matchName}>{p.nameEl}</Text>
          <View style={s.matchBarBg}><View style={[s.matchBarFill, { width: `${p.score}%`, backgroundColor: p.color }]} /></View>
          <Text style={s.matchPct}>{p.score}%</Text>
        </View>
      ))}

      <View style={s.statsRow}>
        <View style={s.statCard}><Text style={s.statVal}>{Math.round(result.confidence * 100)}%</Text><Text style={s.statLabel}>Βεβαιότητα</Text></View>
        <View style={s.statCard}><Text style={s.statVal}>{Math.round(result.consistency * 100)}%</Text><Text style={s.statLabel}>Συνέπεια</Text></View>
      </View>

      <TouchableOpacity style={s.retakeBtn} onPress={restart}>
        <Text style={s.retakeBtnText}>Επανάληψη</Text>
      </TouchableOpacity>

      <Text style={s.privacy}>🔒 Τα δεδομένα μένουν αποκλειστικά στη συσκευή σας.</Text>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 40 },
  progressBar: { height: 6, backgroundColor: colors.surfaceElevated, borderRadius: 3, margin: 16 },
  progressFill: { height: 6, backgroundColor: colors.primary, borderRadius: 3 },
  progressText: { textAlign: "center", fontSize: 13, color: colors.textSecondary, marginBottom: 16 },
  questionCard: { backgroundColor: colors.surface, borderRadius: 16, padding: 24, marginHorizontal: 16, marginBottom: 24, borderWidth: 1, borderColor: colors.border, minHeight: 120, justifyContent: "center" },
  questionText: { fontSize: 17, fontWeight: "700", color: colors.text, lineHeight: 26, textAlign: "center" },
  optionsRow: { flexDirection: "row", justifyContent: "center", gap: 6, paddingHorizontal: 12, flexWrap: "wrap" },
  optionBtn: { flex: 1, minWidth: 60, maxWidth: 72, backgroundColor: colors.surface, borderRadius: 10, padding: 10, alignItems: "center", borderWidth: 2, borderColor: colors.border },
  optionSelected: { borderColor: colors.primary, backgroundColor: colors.primaryLight },
  optionText: { fontSize: 10, fontWeight: "700", color: colors.textSecondary, textAlign: "center" },
  optionTextSelected: { color: colors.primary },
  backBtn: { alignItems: "center", padding: 16, marginTop: 8 },
  backBtnText: { color: colors.textSecondary, fontWeight: "600" },
  resultTitle: { fontSize: 22, fontWeight: "900", color: colors.text, textAlign: "center", marginBottom: 4 },
  quadrantLabel: { fontSize: 14, fontWeight: "700", color: colors.primary, textAlign: "center", marginBottom: 16 },
  compassGrid: { alignItems: "center", marginVertical: 16 },
  compassInner: { flexDirection: "row", alignItems: "center" },
  compassBox: { width: 260, height: 260, borderWidth: 1, borderColor: colors.border, borderRadius: 8, position: "relative", overflow: "hidden" },
  quadrant: { position: "absolute", width: "50%", height: "50%" },
  axisH: { position: "absolute", top: "50%", left: 0, right: 0, height: 1, backgroundColor: colors.border },
  axisV: { position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, backgroundColor: colors.border },
  partyDot: { position: "absolute", width: 10, height: 10, borderRadius: 5, marginLeft: -5, marginBottom: -5 },
  partyLabel: { position: "absolute", top: -14, left: -8, fontSize: 8, fontWeight: "800", color: colors.textSecondary },
  userDot: { position: "absolute", width: 16, height: 16, borderRadius: 8, backgroundColor: colors.primary, marginLeft: -8, marginBottom: -8, borderWidth: 3, borderColor: "#fff", shadowColor: colors.primary, shadowRadius: 6, shadowOpacity: 0.5, elevation: 4 },
  axisLabelTop: { fontSize: 10, color: colors.textTertiary, marginBottom: 4 },
  axisLabelBottom: { fontSize: 10, color: colors.textTertiary, marginTop: 4 },
  axisLabelLeft: { fontSize: 10, color: colors.textTertiary, marginRight: 6, width: 40, textAlign: "right" },
  axisLabelRight: { fontSize: 10, color: colors.textTertiary, marginLeft: 6, width: 40 },
  description: { fontSize: 14, color: colors.textSecondary, textAlign: "center", marginVertical: 12 },
  sectionTitle: { fontSize: 16, fontWeight: "800", color: colors.text, marginTop: 20, marginBottom: 10 },
  matchRow: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  matchName: { width: 70, fontSize: 12, fontWeight: "700", color: colors.text },
  matchBarBg: { flex: 1, height: 10, backgroundColor: colors.surfaceElevated, borderRadius: 5, marginHorizontal: 8, overflow: "hidden" },
  matchBarFill: { height: 10, borderRadius: 5 },
  matchPct: { width: 35, fontSize: 12, fontWeight: "800", color: colors.text, textAlign: "right" },
  statsRow: { flexDirection: "row", gap: 10, marginTop: 16 },
  statCard: { flex: 1, backgroundColor: colors.surface, borderRadius: 10, padding: 12, alignItems: "center", borderWidth: 1, borderColor: colors.border },
  statVal: { fontSize: 18, fontWeight: "900", color: colors.primary },
  statLabel: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  retakeBtn: { backgroundColor: colors.surfaceElevated, borderRadius: 12, padding: 14, alignItems: "center", marginTop: 20 },
  retakeBtnText: { color: colors.textSecondary, fontWeight: "700", fontSize: 14 },
  privacy: { fontSize: 11, color: colors.textTertiary, textAlign: "center", marginTop: 16 },
});
