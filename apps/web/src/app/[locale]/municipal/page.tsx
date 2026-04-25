"use client";
import { useState, useEffect } from "react";
import { useLocale } from "next-intl";
import Link from "next/link";
import { municipal } from "@/lib/api";

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

export default function MunicipalPage() {
  const locale = useLocale();
  const [periferias, setPeriferias] = useState<Periferia[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [dimoi, setDimoi] = useState<Dimos[]>([]);
  const [loading, setLoading] = useState(true);
  const [dimoiLoading, setDimoiLoading] = useState(false);

  const el = (a: string, b: string) => locale === "el" ? a : b;

  useEffect(() => {
    municipal.periferias()
      .then((data: Periferia[]) => setPeriferias(data))
      .finally(() => setLoading(false));
  }, []);

  async function loadDimoi(id: number) {
    setSelected(id);
    setDimoiLoading(true);
    try {
      const data: Dimos[] = await municipal.dimoi(id);
      setDimoi(data);
    } finally {
      setDimoiLoading(false);
    }
  }

  if (loading) return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-gray-400 animate-pulse">{el("Φόρτωση...", "Loading...")}</div>
    </main>
  );

  const selectedPeriferia = periferias.find(p => p.id === selected);

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-6 py-8">
        <div className="flex justify-between items-center mb-6">
          <Link href="bills" className="text-blue-600 text-sm hover:text-blue-700 font-medium">
            ← {el("Νομοσχέδια", "Bills")}
          </Link>
          <div className="flex gap-3 items-center">
            <Link href="mp" className="text-xs text-gray-400 hover:text-blue-600 transition-colors">
              {el("Κόμματα", "Parties")}
            </Link>
            <h1 className="text-sm font-bold text-gray-600">{el("Τοπική Αυτοδιοίκηση", "Municipal Governance")}</h1>
          </div>
        </div>

        <p className="text-gray-500 text-sm mb-6">
          {el(
            "Περιφέρειες και Δήμοι της Ελλάδας — MOD-16. Επιλέξτε μια περιφέρεια για να δείτε τους δήμους.",
            "Regions and Municipalities of Greece — MOD-16. Select a region to view its municipalities."
          )}
        </p>

        {/* Periferia Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-6">
          {periferias.map(p => (
            <button
              key={p.id}
              onClick={() => loadDimoi(p.id)}
              className={`text-left px-3 py-2 rounded-lg text-sm transition-colors border ${
                selected === p.id
                  ? "border-blue-400 bg-blue-50 text-blue-700"
                  : "border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:shadow-sm"
              }`}
            >
              <div className="font-medium">{locale === "el" ? p.name_el : (p.name_en || p.name_el)}</div>
              <div className="text-xs text-gray-400">{p.code}</div>
            </button>
          ))}
        </div>

        {/* Dimoi List */}
        {selected && (
          <div className="border border-gray-200 rounded-xl p-4 bg-white">
            <h2 className="text-lg font-bold text-gray-900 mb-3">
              {locale === "el"
                ? selectedPeriferia?.name_el
                : (selectedPeriferia?.name_en || selectedPeriferia?.name_el)}
            </h2>

            {dimoiLoading ? (
              <div className="text-gray-400 animate-pulse text-sm">{el("Φόρτωση δήμων...", "Loading municipalities...")}</div>
            ) : dimoi.length === 0 ? (
              <div className="text-gray-500 text-sm">{el("Δεν βρέθηκαν δήμοι", "No municipalities found")}</div>
            ) : (
              <div className="space-y-2">
                {dimoi.map(d => (
                  <div key={d.id} className="flex justify-between items-center px-3 py-2 bg-gray-50 rounded-lg">
                    <div>
                      <span className="text-sm font-medium text-gray-900">{locale === "el" ? d.name_el : (d.name_en || d.name_el)}</span>
                    </div>
                    {d.population && (
                      <span className="text-xs text-gray-400">
                        {d.population.toLocaleString()} {el("κάτ.", "pop.")}
                      </span>
                    )}
                  </div>
                ))}
                <div className="text-center text-xs text-gray-400 mt-2">
                  {dimoi.length} {el("δήμοι", "municipalities")}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="mt-8 text-center text-xs text-gray-400">
          MOD-16 · {el("Δεδομένα από Ελληνική Διοίκηση", "Data from Greek Administration")} · API: /api/v1/periferia
        </div>
      </div>

      <footer className="border-t border-gray-200 px-6 py-6 text-center text-xs text-gray-400 mt-8">
        <p>{el("Μη κρατική εφαρμογή — ενημερωτικός χαρακτήρας", "Non-governmental application — informational purposes only")}</p>
        <p className="mt-1">© 2026 Vendetta Labs — MIT License — <a href="https://github.com/NeaBouli/pnyx" className="hover:text-gray-600" target="_blank">Open Source</a></p>
      </footer>
    </main>
  );
}
