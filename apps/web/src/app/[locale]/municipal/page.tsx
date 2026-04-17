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
    <main className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <div className="text-gray-400 animate-pulse">{el("Φόρτωση...", "Loading...")}</div>
    </main>
  );

  const selectedPeriferia = periferias.find(p => p.id === selected);

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-2xl mx-auto px-6 py-8">
        <div className="flex justify-between items-center mb-6">
          <Link href="../bills" className="text-blue-400 text-sm hover:text-blue-300">
            ← {el("Νομοσχέδια", "Bills")}
          </Link>
          <h1 className="text-xl font-bold">{el("Τοπική Αυτοδιοίκηση", "Municipal Governance")}</h1>
        </div>

        <p className="text-gray-400 text-sm mb-6">
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
                  ? "border-blue-500 bg-blue-500/10 text-blue-300"
                  : "border-gray-800 bg-gray-900 text-gray-300 hover:border-gray-600"
              }`}
            >
              <div className="font-medium">{locale === "el" ? p.name_el : (p.name_en || p.name_el)}</div>
              <div className="text-xs text-gray-500">{p.code}</div>
            </button>
          ))}
        </div>

        {/* Dimoi List */}
        {selected && (
          <div className="border border-gray-800 rounded-xl p-4">
            <h2 className="text-lg font-bold mb-3">
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
                  <div key={d.id} className="flex justify-between items-center px-3 py-2 bg-gray-900 rounded-lg">
                    <div>
                      <span className="text-sm font-medium">{locale === "el" ? d.name_el : (d.name_en || d.name_el)}</span>
                    </div>
                    {d.population && (
                      <span className="text-xs text-gray-500">
                        {d.population.toLocaleString()} {el("κάτ.", "pop.")}
                      </span>
                    )}
                  </div>
                ))}
                <div className="text-center text-xs text-gray-600 mt-2">
                  {dimoi.length} {el("δήμοι", "municipalities")}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="mt-8 text-center text-xs text-gray-600">
          MOD-16 · {el("Δεδομένα από Ελληνική Διοίκηση", "Data from Greek Administration")} · API: /api/v1/periferia
        </div>
      </div>
    </main>
  );
}
