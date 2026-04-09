/**
 * Liquid Political Compass — Type Definitions
 * Rein clientseitig, niemals an den Server gesendet.
 */

/** Verfügbare Kompass-Modelle */
export type CompassModel =
  | "party-match"      // Parteizugehörigkeit (% Match mit 8 Parteien)
  | "left-right"       // Links-Rechts-Achse
  | "compass-2d"       // 2D: Wirtschaft × Gesellschaft
  | "thematic-radar";  // Radar nach Politikbereichen

/** Thematische Bereiche für Radar-Modell */
export type ThematicArea =
  | "economy"         // Οικονομία
  | "social"          // Κοινωνική Πολιτική
  | "environment"     // Περιβάλλον
  | "governance"      // Δημοκρατία & Διακυβέρνηση
  | "security"        // Ασφάλεια & Άμυνα
  | "culture"         // Πολιτισμός & Παιδεία
  | "infrastructure"; // Υποδομές & Μεταφορές

/** Mapping einer Kategorie zu politischen Dimensionen */
export interface DimensionMapping {
  /** Links(-1) ↔ Rechts(+1): Richtung in der die Zustimmung tendiert */
  leftRight: number;
  /** Wirtschaft: Staat(-1) ↔ Markt(+1) */
  economic: number;
  /** Gesellschaft: Liberal(-1) ↔ Konservativ(+1) */
  social: number;
  /** Thematischer Bereich */
  thematicArea: ThematicArea;
}

/** Akkumuliertes Signal pro Kategorie */
export interface CategorySignal {
  category: string;
  weightedSum: number;
  voteCount: number;
}

/** Einzelner Bill-Vote-Eintrag im Kompass */
export interface BillCompassEntry {
  billId: string;
  vote: "YES" | "NO" | "ABSTAIN";
  categories: string[];
  votedAt: string;
}

/** Vollständiges Kompass-Profil (verschlüsselt in localStorage) */
export interface CompassProfile {
  version: 1;
  createdAt: string;
  updatedAt: string;
  selectedModel: CompassModel | null;
  signals: Record<string, CategorySignal>;
  vaaAnswers: Record<number, number> | null;
  vaaCompletedAt: string | null;
  billVotes: BillCompassEntry[];
}

/** Ergebnis: Parteimatch */
export interface PartyMatchResult {
  partyId: number;
  nameEl: string;
  abbreviation: string;
  colorHex: string;
  matchPercent: number;
}

/** Ergebnis: Links-Rechts */
export interface LeftRightResult {
  position: number; // -1 (links) bis +1 (rechts)
  dataPoints: number;
}

/** Ergebnis: 2D-Kompass */
export interface Compass2DResult {
  economic: number; // -1 (Staat) bis +1 (Markt)
  social: number;   // -1 (liberal) bis +1 (konservativ)
  dataPoints: number;
}

/** Ergebnis: Thematischer Radar */
export interface ThematicRadarResult {
  areas: Record<ThematicArea, { position: number; dataPoints: number }>;
}

/** Union aller Ergebnistypen */
export type CompassResult =
  | { model: "party-match"; data: PartyMatchResult[] }
  | { model: "left-right"; data: LeftRightResult }
  | { model: "compass-2d"; data: Compass2DResult }
  | { model: "thematic-radar"; data: ThematicRadarResult };
