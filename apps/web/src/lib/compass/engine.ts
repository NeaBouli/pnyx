/**
 * Compass Engine — Berechnet alle 4 Kompass-Modelle rein clientseitig.
 * Keine Serveraufrufe, keine externen Abhängigkeiten.
 */
import type {
  CompassProfile,
  CompassResult,
  CategorySignal,
  PartyMatchResult,
  LeftRightResult,
  Compass2DResult,
  ThematicRadarResult,
  ThematicArea,
  CompassModel,
} from "./types";
import { getDimensionMapping, THEMATIC_LABELS } from "./dimension-map";

// ─── Hilfsfunktionen ────────────────────────────────────────────────────────

/** Normalisiert einen Wert auf [-1, +1] */
function clamp(v: number): number {
  return Math.max(-1, Math.min(1, v));
}

/** Berechnet den gewichteten Durchschnitt aus einem Signal */
function signalAvg(signal: CategorySignal): number {
  if (signal.voteCount === 0) return 0;
  return signal.weightedSum / signal.voteCount;
}

/** Sammelt alle Signale mit gültigem Dimensions-Mapping */
function getWeightedSignals(signals: Record<string, CategorySignal>) {
  return Object.values(signals)
    .filter(s => s.voteCount > 0)
    .map(s => ({ signal: s, mapping: getDimensionMapping(s.category) }))
    .filter((x): x is { signal: CategorySignal; mapping: NonNullable<ReturnType<typeof getDimensionMapping>> } =>
      x.mapping !== null
    );
}

// ─── Profil-Mutation ────────────────────────────────────────────────────────

/** Erstellt ein leeres Kompass-Profil */
export function createEmptyProfile(): CompassProfile {
  return {
    version: 1,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    selectedModel: null,
    signals: {},
    vaaAnswers: null,
    vaaCompletedAt: null,
    billVotes: [],
  };
}

/** Fügt VAA-Antworten in das Profil ein */
export function seedFromVAA(
  profile: CompassProfile,
  answers: Record<number, number>,
  statementCategories: Record<number, string>
): CompassProfile {
  const updated = { ...profile, vaaAnswers: answers, vaaCompletedAt: new Date().toISOString() };
  const signals = { ...updated.signals };

  for (const [idStr, value] of Object.entries(answers)) {
    if (value === 0) continue; // Neutral überspringen
    const category = statementCategories[Number(idStr)];
    if (!category) continue;

    if (!signals[category]) {
      signals[category] = { category, weightedSum: 0, voteCount: 0 };
    }
    signals[category] = {
      ...signals[category],
      weightedSum: signals[category].weightedSum + value,
      voteCount: signals[category].voteCount + 1,
    };
  }

  return { ...updated, signals, updatedAt: new Date().toISOString() };
}

/** Fügt einen Bill-Vote in das Profil ein */
export function recordBillVote(
  profile: CompassProfile,
  billId: string,
  vote: "YES" | "NO" | "ABSTAIN",
  categories: string[]
): CompassProfile {
  if (vote === "ABSTAIN") return profile; // Enthaltung ändert Kompass nicht

  const voteValue = vote === "YES" ? 1 : -1;
  const signals = { ...profile.signals };

  for (const category of categories) {
    if (!getDimensionMapping(category)) continue;
    if (!signals[category]) {
      signals[category] = { category, weightedSum: 0, voteCount: 0 };
    }
    signals[category] = {
      ...signals[category],
      weightedSum: signals[category].weightedSum + voteValue,
      voteCount: signals[category].voteCount + 1,
    };
  }

  const billVotes = [
    ...profile.billVotes,
    { billId, vote, categories, votedAt: new Date().toISOString() },
  ];

  return { ...profile, signals, billVotes, updatedAt: new Date().toISOString() };
}

// ─── Berechnungen ───────────────────────────────────────────────────────────

/** Zählt die Datenpunkte im Profil */
export function getDataPointCount(profile: CompassProfile): number {
  return Object.values(profile.signals).reduce((sum, s) => sum + s.voteCount, 0);
}

/** Links-Rechts-Berechnung */
export function computeLeftRight(profile: CompassProfile): LeftRightResult {
  const entries = getWeightedSignals(profile.signals);
  if (entries.length === 0) return { position: 0, dataPoints: 0 };

  let totalWeight = 0;
  let weightedSum = 0;

  for (const { signal, mapping } of entries) {
    const avg = signalAvg(signal);
    const contribution = avg * mapping.leftRight;
    weightedSum += contribution * signal.voteCount;
    totalWeight += signal.voteCount;
  }

  return {
    position: clamp(totalWeight > 0 ? weightedSum / totalWeight : 0),
    dataPoints: totalWeight,
  };
}

/** 2D-Kompass-Berechnung */
export function computeCompass2D(profile: CompassProfile): Compass2DResult {
  const entries = getWeightedSignals(profile.signals);
  if (entries.length === 0) return { economic: 0, social: 0, dataPoints: 0 };

  let ecoSum = 0, socSum = 0, totalWeight = 0;

  for (const { signal, mapping } of entries) {
    const avg = signalAvg(signal);
    ecoSum += avg * mapping.economic * signal.voteCount;
    socSum += avg * mapping.social * signal.voteCount;
    totalWeight += signal.voteCount;
  }

  return {
    economic: clamp(totalWeight > 0 ? ecoSum / totalWeight : 0),
    social: clamp(totalWeight > 0 ? socSum / totalWeight : 0),
    dataPoints: totalWeight,
  };
}

/** Thematisches Radar */
export function computeThematicRadar(profile: CompassProfile): ThematicRadarResult {
  const areas: ThematicRadarResult["areas"] = {} as ThematicRadarResult["areas"];

  for (const key of Object.keys(THEMATIC_LABELS) as ThematicArea[]) {
    areas[key] = { position: 0, dataPoints: 0 };
  }

  for (const signal of Object.values(profile.signals)) {
    if (signal.voteCount === 0) continue;
    const mapping = getDimensionMapping(signal.category);
    if (!mapping) continue;

    const area = areas[mapping.thematicArea];
    const avg = signalAvg(signal);
    area.position = (area.position * area.dataPoints + avg * signal.voteCount) / (area.dataPoints + signal.voteCount);
    area.dataPoints += signal.voteCount;
  }

  // Normalisieren
  for (const key of Object.keys(areas) as ThematicArea[]) {
    areas[key].position = clamp(areas[key].position);
  }

  return { areas };
}

/** Parteimatch (client-side, wie vaa.py calculate_match) */
export function computePartyMatch(
  profile: CompassProfile,
  partyPositions: Record<string, Record<number, number>>, // abbreviation → {statementId → position}
  partyMeta: Record<string, { id: number; nameEl: string; colorHex: string }>
): PartyMatchResult[] {
  const answers = profile.vaaAnswers;
  if (!answers) return [];

  const results: PartyMatchResult[] = [];

  for (const [abbr, positions] of Object.entries(partyPositions)) {
    const meta = partyMeta[abbr];
    if (!meta) continue;

    let matches = 0;
    let total = 0;

    for (const [stmtIdStr, userPos] of Object.entries(answers)) {
      if (userPos === 0) continue;
      const partyPos = positions[Number(stmtIdStr)];
      if (partyPos === undefined) continue;
      total++;
      if (userPos === partyPos) matches++;
    }

    results.push({
      partyId: meta.id,
      nameEl: meta.nameEl,
      abbreviation: abbr,
      colorHex: meta.colorHex,
      matchPercent: total > 0 ? Math.round((matches / total) * 1000) / 10 : 0,
    });
  }

  return results.sort((a, b) => b.matchPercent - a.matchPercent);
}

/** Berechnet das Ergebnis für das gewählte Modell */
export function computeResult(
  profile: CompassProfile,
  model: CompassModel,
  partyPositions?: Record<string, Record<number, number>>,
  partyMeta?: Record<string, { id: number; nameEl: string; colorHex: string }>
): CompassResult | null {
  if (getDataPointCount(profile) === 0) return null;

  switch (model) {
    case "party-match":
      if (!partyPositions || !partyMeta) return null;
      return { model, data: computePartyMatch(profile, partyPositions, partyMeta) };
    case "left-right":
      return { model, data: computeLeftRight(profile) };
    case "compass-2d":
      return { model, data: computeCompass2D(profile) };
    case "thematic-radar":
      return { model, data: computeThematicRadar(profile) };
  }
}
