/**
 * Dimension Map — Ordnet griechische Kategorien politischen Dimensionen zu.
 * Basiert auf den realen Positionen der 8 griechischen Parteien (2024-2026).
 *
 * leftRight: -1 = Links (Staatsintervention, Umverteilung)
 *            +1 = Rechts (Markt, Tradition, Sicherheit)
 * economic:  -1 = Staat/Regulierung, +1 = Markt/Deregulierung
 * social:    -1 = Liberal/Progressiv, +1 = Konservativ/Traditionell
 */
import type { DimensionMapping, ThematicArea } from "./types";

const DIMENSION_MAP: Record<string, DimensionMapping> = {
  // ─── Wirtschaft & Arbeit ──────────────────────────────────────────────
  "Εργασία & Οικονομία":       { leftRight: -0.6, economic: -0.7, social:  0.0, thematicArea: "economy" },
  "Φορολογική Πολιτική":       { leftRight: -0.5, economic: -0.6, social:  0.0, thematicArea: "economy" },
  "Οικονομική Πολιτική":       { leftRight: -0.4, economic: -0.5, social:  0.0, thematicArea: "economy" },
  "Αγροτική Πολιτική":         { leftRight: -0.3, economic: -0.4, social:  0.2, thematicArea: "economy" },
  "Εργασία & Δημογραφία":      { leftRight: -0.3, economic: -0.3, social:  0.0, thematicArea: "economy" },
  "Ναυτιλία & Περιβάλλον":     { leftRight: -0.2, economic: -0.3, social:  0.0, thematicArea: "economy" },

  // ─── Gesellschaft & Soziales ──────────────────────────────────────────
  "Κοινωνική Πολιτική":        { leftRight: -0.5, economic: -0.4, social: -0.5, thematicArea: "social" },
  "Υγεία":                     { leftRight: -0.4, economic: -0.5, social:  0.0, thematicArea: "social" },
  "Στέγαση":                   { leftRight: -0.5, economic: -0.6, social:  0.0, thematicArea: "social" },
  "Δημογραφία":                { leftRight:  0.2, economic:  0.0, social:  0.4, thematicArea: "social" },
  "Ζωικά Δικαιώματα":          { leftRight: -0.1, economic:  0.0, social: -0.3, thematicArea: "social" },
  "Δημόσιες Υπηρεσίες":       { leftRight: -0.6, economic: -0.7, social:  0.0, thematicArea: "social" },

  // ─── Umwelt & Klima ───────────────────────────────────────────────────
  "Περιβάλλον & Ενέργεια":     { leftRight: -0.3, economic: -0.2, social: -0.2, thematicArea: "environment" },
  "Περιβάλλον & Κλιματική Πολιτική": { leftRight: -0.3, economic: -0.3, social: -0.1, thematicArea: "environment" },

  // ─── Demokratie & Governance ──────────────────────────────────────────
  "Δημοκρατία":                { leftRight:  0.0, economic:  0.0, social: -0.5, thematicArea: "governance" },
  "Δημοκρατία & Ελευθερία Τύπου": { leftRight: -0.2, economic:  0.0, social: -0.7, thematicArea: "governance" },
  "Ψηφιακή Διακυβέρνηση":     { leftRight:  0.0, economic:  0.1, social: -0.3, thematicArea: "governance" },
  "Υποδομές & Λογοδοσία":     { leftRight: -0.2, economic:  0.0, social: -0.4, thematicArea: "governance" },

  // ─── Sicherheit & Außenpolitik ────────────────────────────────────────
  "Άμυνα & Εξωτερική Πολιτική": { leftRight:  0.5, economic:  0.1, social:  0.4, thematicArea: "security" },
  "Δικαιοσύνη & Ασφάλεια":    { leftRight:  0.0, economic:  0.0, social: -0.3, thematicArea: "security" },
  "Μετανάστευση":              { leftRight: -0.3, economic:  0.0, social: -0.5, thematicArea: "security" },
  "Ευρωπαϊκή Πολιτική":       { leftRight: -0.1, economic: -0.2, social: -0.2, thematicArea: "security" },

  // ─── Kultur & Bildung ─────────────────────────────────────────────────
  "Παιδεία":                   { leftRight:  0.3, economic:  0.4, social:  0.1, thematicArea: "culture" },
  "Πολιτισμός":                { leftRight: -0.1, economic: -0.2, social:  0.2, thematicArea: "culture" },
  "Εκκλησία & Κράτος":        { leftRight: -0.2, economic:  0.0, social: -0.6, thematicArea: "culture" },
  "Εθνικά Θέματα":            { leftRight:  0.3, economic:  0.0, social:  0.3, thematicArea: "culture" },

  // ─── Infrastruktur & Regionen ─────────────────────────────────────────
  "Τουρισμός":                 { leftRight:  0.0, economic:  0.1, social:  0.0, thematicArea: "infrastructure" },
  "Μεταφορές":                 { leftRight: -0.3, economic: -0.4, social:  0.0, thematicArea: "infrastructure" },
  "Μεταφορές & Νησιωτική Πολιτική": { leftRight: -0.3, economic: -0.4, social:  0.0, thematicArea: "infrastructure" },
  "Περιφερειακή Ανάπτυξη":    { leftRight: -0.2, economic: -0.3, social:  0.0, thematicArea: "infrastructure" },
};

/**
 * Holt das Dimensions-Mapping für eine Kategorie.
 * Gibt null zurück wenn die Kategorie unbekannt ist.
 */
export function getDimensionMapping(category: string): DimensionMapping | null {
  return DIMENSION_MAP[category] ?? null;
}

/** Alle bekannten Kategorien */
export function getKnownCategories(): string[] {
  return Object.keys(DIMENSION_MAP);
}

/** Thematische Bereich-Labels (el/en) */
export const THEMATIC_LABELS: Record<ThematicArea, { el: string; en: string }> = {
  economy:        { el: "Οικονομία",         en: "Economy" },
  social:         { el: "Κοινωνία",          en: "Society" },
  environment:    { el: "Περιβάλλον",        en: "Environment" },
  governance:     { el: "Διακυβέρνηση",      en: "Governance" },
  security:       { el: "Ασφάλεια",          en: "Security" },
  culture:        { el: "Πολιτισμός",        en: "Culture" },
  infrastructure: { el: "Υποδομές",          en: "Infrastructure" },
};

/** Kompass-Modell-Labels (el/en) */
export const MODEL_LABELS: Record<string, { el: string; en: string; desc_el: string; desc_en: string }> = {
  "party-match":     { el: "Κομματική Συμφωνία",  en: "Party Match",       desc_el: "Ποσοστό συμφωνίας με κάθε κόμμα",         desc_en: "Match percentage with each party" },
  "left-right":      { el: "Αριστερά — Δεξιά",    en: "Left — Right",      desc_el: "Μονοδιάστατο πολιτικό φάσμα",             desc_en: "Single-axis political spectrum" },
  "compass-2d":      { el: "Πολιτική Πυξίδα 2D",  en: "2D Compass",        desc_el: "Οικονομία × Κοινωνία σε δύο άξονες",     desc_en: "Economy × Society on two axes" },
  "thematic-radar":  { el: "Θεματικό Ραντάρ",     en: "Thematic Radar",    desc_el: "Θέση ανά πολιτικό τομέα",                 desc_en: "Position per policy area" },
};

export default DIMENSION_MAP;
