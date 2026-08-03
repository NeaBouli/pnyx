import type { ConsensusRepresentationView } from "./api";

export type ConsensusViewKey = "municipal" | "regional" | "national";

export const CONSENSUS_VIEW_LABELS: Record<ConsensusViewKey, string> = {
  municipal: "Ο Δήμος μου",
  regional: "Η Περιφέρειά μου",
  national: "Όλη η Ελλάδα",
};

export function consensusScoreLabel(score: number | null): string {
  if (score === null) return "Χωρίς αξιολογήσεις";
  if (score >= 2) return "Ισχυρή συναίνεση";
  if (score > 0) return "Θετική τάση";
  if (score === 0) return "Ουδέτερη τάση";
  if (score > -2) return "Αρνητική τάση";
  return "Ισχυρή διαφωνία";
}

export function unavailableViewMessage(view: ConsensusRepresentationView): string | null {
  if (view.available) return null;
  return view.view === "municipal"
    ? "Ορίστε Δήμο στο Προφίλ για να δείτε τα τοπικά αποτελέσματα."
    : "Ορίστε Περιφέρεια στο Προφίλ για να δείτε τα περιφερειακά αποτελέσματα.";
}
