"use client";

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import Link from "next/link";
import { municipal, type ConsensusRepresentationResponse } from "@/lib/api";

interface Periferia {
  id: number;
  name_el: string;
  name_en: string | null;
  code: string;
}

interface Dimos {
  id: number;
  name_el: string;
  name_en: string | null;
  population: number | null;
}

type Scope = "municipal" | "regional" | "national";

export default function MunicipalPage() {
  const locale = useLocale();
  const [periferias, setPeriferias] = useState<Periferia[]>([]);
  const [selectedPeriferia, setSelectedPeriferia] = useState<number | null>(null);
  const [selectedDimos, setSelectedDimos] = useState<number | null>(null);
  const [dimoi, setDimoi] = useState<Dimos[]>([]);
  const [scope, setScope] = useState<Scope>("national");

  const [loading, setLoading] = useState(true);
  const [dimoiLoading, setDimoiLoading] = useState(false);
  const [consensusLoading, setConsensusLoading] = useState(true);
  const [dimoiError, setDimoiError] = useState<string | null>(null);
  const [consensusError, setConsensusError] = useState<string | null>(null);
  const [consensus, setConsensus] = useState<ConsensusRepresentationResponse | null>(null);

  const localeEl = locale === "el";
  const selectedPeriferiaData = periferias.find((p) => p.id === selectedPeriferia);
  const selectedDimosData = dimoi.find((d) => d.id === selectedDimos);

  const activeView = consensus?.views[scope];

  const tabLabel = (scopeId: Scope) => {
    if (scopeId === "municipal") return localeEl ? "Δήμος" : "Municipal";
    if (scopeId === "regional") return localeEl ? "Περιφέρεια" : "Regional";
    return localeEl ? "Εθνικό" : "National";
  };

  const t = (el: string, en: string) => (localeEl ? el : en);

  useEffect(() => {
    municipal.periferias()
      .then((data: Periferia[]) => setPeriferias(data))
      .catch(() => setDimoiError(
        localeEl ? "Η λίστα περιφερειών δεν είναι διαθέσιμη." : "Regions list is unavailable.",
      ))
      .finally(() => setLoading(false));
  }, [localeEl]);

  async function loadDimoi(periferiaId: number) {
    setSelectedPeriferia(periferiaId);
    setSelectedDimos(null);
    setDimoiLoading(true);
    setDimoiError(null);

    try {
      const data: Dimos[] = await municipal.dimoi(periferiaId);
      setDimoi(data);
    } catch {
      setDimoiError(
        t("Αποτυχία φόρτωσης δήμων.", "Failed to load municipalities."),
      );
    } finally {
      setDimoiLoading(false);
    }
  }

  useEffect(() => {
    const params =
      scope === "municipal"
        ? selectedDimos !== null && selectedPeriferia !== null
          ? { dimos_id: selectedDimos, periferia_id: selectedPeriferia }
          : selectedPeriferia !== null
            ? { periferia_id: selectedPeriferia }
            : {}
        : scope === "regional" && selectedPeriferia !== null
          ? { periferia_id: selectedPeriferia }
          : {};

    setConsensusLoading(true);
    setConsensusError(null);

    municipal.getConsensusRepresentation(params)
      .then((data) => setConsensus(data))
      .catch(() => setConsensusError(
        localeEl ? "Αποτυχία λήψης δεδομένων συμφωνίας." : "Failed to load consensus representation.",
      ))
      .finally(() => setConsensusLoading(false));
  }, [scope, selectedPeriferia, selectedDimos, localeEl]);

  const setScopeAndKeepSelection = (nextScope: Scope) => {
    setScope(nextScope);
    if (nextScope === "national") {
      setSelectedDimos(null);
    }
  };

  const showDimoiSelector = selectedPeriferia !== null;

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex justify-between items-center mb-6">
          <Link href="bills" className="text-blue-600 text-sm hover:text-blue-700 font-medium">
            ← {t("Νομοσχέδια", "Bills")}
          </Link>
          <div className="flex gap-3 items-center">
            <Link href="mp" className="text-xs text-gray-400 hover:text-blue-600 transition-colors">
              {t("Κόμματα", "Parties")}
            </Link>
            <h1 className="text-sm font-bold text-gray-600">{t("Τοπική Αυτοδιοίκηση", "Municipal Governance")}</h1>
          </div>
        </div>

        <p className="text-gray-500 text-sm mb-4">
          {t(
            "Μηνιαία ανάλυση DIAVGEIA κατά Δήμο, Περιφέρεια και Εθνικό επίπεδο (Μόνο σύνοψη, χωρίς αποτύπωση ατομικών ψήφων).",
            "DIAVGEIA consensus overview by municipality, region, and national scope (aggregate-only, no individual votes).",
          )}
        </p>

        <div className="flex flex-wrap gap-2 mb-4">
          {(["municipal", "regional", "national"] as Scope[]).map((scopeId) => (
            <button
              key={scopeId}
              type="button"
              onClick={() => setScopeAndKeepSelection(scopeId)}
              className={`px-3 py-2 text-sm rounded-lg border transition-colors ${
                scope === scopeId
                  ? "border-blue-400 bg-blue-50 text-blue-700"
                  : "border-gray-200 text-gray-600 hover:border-gray-300"
              }`}
            >
              {tabLabel(scopeId)}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-4">
          {periferias.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => loadDimoi(p.id)}
              className={`text-left px-3 py-2 rounded-lg border transition-colors ${
                selectedPeriferia === p.id
                  ? "border-blue-400 bg-blue-50 text-blue-700"
                  : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:shadow-sm"
              }`}
            >
              <div className="font-medium text-sm">{localeEl ? p.name_el : (p.name_en || p.name_el)}</div>
              <div className="text-xs text-gray-400">{p.code}</div>
            </button>
          ))}
        </div>

        {dimoiError && <div className="text-xs text-red-500 mb-4">{dimoiError}</div>}

        {showDimoiSelector ? (
          <div className="border border-gray-200 rounded-lg p-4 bg-white mb-6">
            <h2 className="text-sm font-bold text-gray-900 mb-3">
              {selectedDimosData
                ? `${localeEl ? selectedDimosData.name_el : (selectedDimosData.name_en || selectedDimosData.name_el)} / `
                  + `${localeEl ? selectedPeriferiaData?.name_el : (selectedPeriferiaData?.name_en || selectedPeriferiaData?.name_el)}`
                : localeEl ? selectedPeriferiaData?.name_el : (selectedPeriferiaData?.name_en || selectedPeriferiaData?.name_el)}
            </h2>

            {dimoiLoading ? (
              <div className="text-gray-400 animate-pulse text-sm">
                {t("Φόρτωση δήμων...", "Loading municipalities...")}
              </div>
            ) : dimoi.length === 0 ? (
              <div className="text-gray-500 text-sm">
                {t("Δεν βρέθηκαν δήμοι", "No municipalities found")}
              </div>
            ) : (
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {dimoi.map((dimos) => (
                  <button
                    key={dimos.id}
                    type="button"
                    onClick={() => setSelectedDimos(selectedDimos === dimos.id ? null : dimos.id)}
                    className={`w-full text-left flex justify-between items-center px-3 py-2 rounded-lg border ${
                      selectedDimos === dimos.id
                        ? "border-blue-300 bg-blue-50 text-blue-700"
                        : "border-gray-100 bg-gray-50 text-gray-700 hover:border-gray-300"
                    }`}
                  >
                    <span className="text-sm font-medium">
                      {localeEl ? dimos.name_el : (dimos.name_en || dimos.name_el)}
                    </span>
                    {dimos.population && (
                      <span className="text-xs text-gray-400">
                        {dimos.population.toLocaleString()} {t("κάτ.", "pop.")}
                      </span>
                    )}
                  </button>
                ))}
                <div className="text-center text-xs text-gray-400 mt-1">
                  {dimoi.length} {t("δήμοι", "municipalities")}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="mb-6 text-xs text-gray-500">
            {t("Επιλέξτε περιοχή για να ενεργοποιήσετε περιφερειακή ή δημοτική προβολή.", "Select a region to enable regional or municipal scope.")}
          </div>
        )}

        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="text-sm font-bold text-gray-900 mb-3">
            {scope === "national"
              ? t("Εθνική οπτική", "National view")
              : scope === "regional"
                ? t("Περιφερειακή οπτική", "Regional view")
                : t("Δημοτική οπτική", "Municipal view")}
          </h3>

          {consensus?.privacy === "aggregate_only" && (
            <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3">
              {t(
                `Ασφαλής προβολή: εμφανίζονται αποτελέσματα μόνο από ${consensus.minimum_group_size} ή περισσότερες αξιολογήσεις ανά θέμα, χωρίς ατομική απόδοση.`,
                `Privacy-safe view: results appear only from ${consensus.minimum_group_size} or more evaluations per item, without individual attribution.`,
              )}
            </div>
          )}

          {loading ? (
            <div className="text-gray-400 animate-pulse text-sm">
              {t("Φόρτωση...", "Loading...")}
            </div>
          ) : consensusLoading ? (
            <div className="text-gray-400 animate-pulse text-sm">
              {t("Ανανέωση δεδομένων...", "Updating consensus data...")}
            </div>
          ) : consensusError ? (
            <div className="text-red-500 text-sm">{consensusError}</div>
          ) : !activeView ? (
            <div className="text-gray-500 text-sm">
              {t("Δεν υπάρχουν δεδομένα για την επιλεγμένη προβολή.", "No data for the selected view.")}
            </div>
          ) : !activeView.available ? (
            <div className="text-gray-500 text-sm">
              {scope === "municipal"
                ? t("Η δημοτική προβολή απαιτεί επιλογή Δήμου.", "Municipal view requires a municipality selection.")
                : t("Η περιφερειακή προβολή απαιτεί επιλογή Περιφέρειας.", "Regional view requires a region selection.")}
            </div>
          ) : (
            <div>
              {scope === "national" && consensus.coverage && (
                <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2 text-xs text-yellow-800 mb-3">
                  {!consensus.coverage.complete_geographic_representation ? (
                    t(
                      "Προσοχή: η εθνική κάλυψη δεν είναι γεωγραφικά πλήρης (ενδέχεται θεσμικά/αντιστοιχισμένα κενά).",
                      "Warning: national coverage is not fully geographic (institutional/unmapped exclusions may apply).",
                    )
                  ) : t(
                    "Πλήρης γεωγραφική κάλυψη DIAVGEIA για το εθνικό σύνολο.",
                    "Full national DIAVGEIA geographic coverage.",
                  )}
                </div>
              )}

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-3">
                <div className="rounded-lg border border-gray-100 bg-gray-50 p-2">
                  <div className="text-[11px] uppercase text-gray-400">{t("Νομοσχέδια", "Bills")}</div>
                  <div className="text-lg font-bold text-gray-900">{activeView.bill_count}</div>
                </div>
                <div className="rounded-lg border border-gray-100 bg-gray-50 p-2">
                  <div className="text-[11px] uppercase text-gray-400">{t("Ψήφοι Σύγκρισης", "Consensus votes")}</div>
                  <div className="text-lg font-bold text-gray-900">{activeView.consensus_vote_count}</div>
                </div>
                <div className="rounded-lg border border-gray-100 bg-gray-50 p-2">
                  <div className="text-[11px] uppercase text-gray-400">{t("Βαθμολογία", "Weighted score")}</div>
                  <div className="text-lg font-bold text-gray-900">
                    {activeView.weighted_score === null ? "—" : activeView.weighted_score.toFixed(1)}
                  </div>
                </div>
              </div>

              {activeView.bill_count === 0 ? (
                <div className="text-gray-500 text-sm">{t("Δεν υπάρχουν διαθέσιμα νομοσχέδια για το τρέχον scope.", "No bills available for the selected scope.")}</div>
              ) : (
                <div className="space-y-2">
                  {activeView.bills.map((bill) => (
                    <div key={bill.bill_id} className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                      <div className="text-sm font-medium text-gray-900">
                        {bill.title_el}
                        {bill.dimos_id && " / Δήμος " + bill.dimos_id}
                      </div>
                      <div className="mt-1 text-xs text-gray-500">
                        {t("Συγκεκριμένη βαθμολογία", "Consensus score")}:
                        {" "}
                        {bill.consensus_score.toFixed(1)} ·
                        {" "}
                        {bill.consensus_count} {t("κρίν.", "votes")}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="mt-8 text-center text-xs text-gray-400">
          MOD-16 · {t("Δεδομένα από Ελληνική Διοίκηση", "Data from Greek Administration")} · API: /api/v1/consensus/representation
        </div>
      </div>

      <footer className="border-t border-gray-200 px-6 py-6 text-center text-xs text-gray-400 mt-8">
        <p>{t("Μη κρατική εφαρμογή — ενημερωτικός χαρακτήρας", "Non-governmental application — informational purposes only")}</p>
        <p className="mt-1">
          © 2026 V-Labs Development — MIT License —{" "}
          <a href="https://github.com/NeaBouli/pnyx" className="hover:text-gray-600" target="_blank">
            Open Source
          </a>
        </p>
      </footer>
    </main>
  );
}
