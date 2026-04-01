"use client";
import { useState, useEffect } from "react";
import { useLocale } from "next-intl";
import Link from "next/link";
import { mp } from "@/lib/api";

export default function MPPage() {
  const locale = useLocale();
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const [ranking, setRanking]           = useState<any[]>([]);
  const [selected, setSelected]         = useState<string | null>(null);
  const [detail, setDetail]             = useState<any>(null);
  const [loading, setLoading]           = useState(true);
  const [detailLoading, setDetailLoad]  = useState(false);

  const el = (a: string, b: string) => locale === "el" ? a : b;

  useEffect(() => {
    mp.ranking().then(r => setRanking(r.ranking || []))
      .finally(() => setLoading(false));
  }, []);

  async function loadDetail(abbr: string) {
    setSelected(abbr); setDetailLoad(true);
    try { setDetail(await mp.compare(abbr)); }
    finally { setDetailLoad(false); }
  }

  if (loading) return (
    <main className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <div className="text-gray-400 animate-pulse">{el("Φόρτωση...", "Loading...")}</div>
    </main>
  );

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex justify-between items-center">
        <Link href="../bills" className="text-blue-400 font-bold">← εκκλησία</Link>
        <h1 className="text-sm font-bold text-gray-300">{el("Κόμματα vs Πολίτες", "Parties vs Citizens")}</h1>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-8">
        <h2 className="text-xl font-bold mb-2">{el("Ποιο κόμμα ψηφίζει όπως οι πολίτες;", "Which party votes like the citizens?")}</h2>
        <p className="text-gray-400 text-sm mb-6">{el("Σύγκριση πλειοψηφίας πολιτών με κοινοβουλευτική ψήφο.", "Comparing citizen majority with parliamentary vote.")}</p>

        {ranking.length > 0 ? (
          <div className="space-y-2 mb-8">
            {ranking.map((r: any) => (
              <button key={r.party_abbr} onClick={() => loadDetail(r.party_abbr)}
                className={`w-full text-left rounded-xl p-4 border transition-all ${
                  selected === r.party_abbr ? "border-blue-500 bg-blue-950" : "border-gray-800 bg-gray-900 hover:border-gray-600"
                }`}>
                <div className="flex items-center gap-3">
                  <span className="text-gray-600 font-bold w-6 text-sm">#{r.rank}</span>
                  <div className="w-3 h-10 rounded-full flex-shrink-0" style={{ backgroundColor: r.color_hex || "#3b82f6" }} />
                  <div className="flex-1">
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-bold">{r.party_name_el}</span>
                      <span className="font-black text-xl" style={{ color: r.color_hex || "#3b82f6" }}>{r.agreement_pct}%</span>
                    </div>
                    <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${r.agreement_pct}%`, backgroundColor: r.color_hex || "#3b82f6" }} />
                    </div>
                    <div className="flex justify-between mt-1 text-xs text-gray-600">
                      <span>{r.bills_agree} {el("σύγκλιση", "agree")} / {r.bills_analyzed - r.bills_agree} {el("απόκλιση", "disagree")}</span>
                      <span>{r.bills_analyzed} bills</span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="bg-gray-900 rounded-xl p-8 text-center text-gray-500 mb-8">
            {el("Δεν υπάρχουν αρκετά δεδομένα.", "Not enough data yet.")}
          </div>
        )}

        {/* Detail */}
        {selected && detail && !detailLoading && (
          <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 mb-8">
            <h3 className="font-bold text-lg mb-1">{detail.party?.name_el}</h3>
            <p className="text-gray-400 text-sm mb-4">{detail.summary?.headline_el}</p>
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="bg-gray-800 rounded-xl p-3 text-center">
                <div className="text-2xl font-black text-blue-400">{detail.summary?.agreement_pct}%</div>
                <div className="text-xs text-gray-500">{el("Σύγκλιση", "Agreement")}</div>
              </div>
              <div className="bg-gray-800 rounded-xl p-3 text-center">
                <div className="text-2xl font-black text-green-400">{detail.summary?.bills_agree}</div>
                <div className="text-xs text-gray-500">{el("Συμφωνεί", "Agrees")}</div>
              </div>
              <div className="bg-gray-800 rounded-xl p-3 text-center">
                <div className="text-2xl font-black text-red-400">{detail.summary?.bills_disagree}</div>
                <div className="text-xs text-gray-500">{el("Διαφωνεί", "Disagrees")}</div>
              </div>
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {(detail.comparisons || []).map((c: any) => (
                <Link key={c.bill_id} href={`../bills/${c.bill_id}`}
                  className="flex items-center gap-3 p-3 bg-gray-800 rounded-xl hover:bg-gray-700 transition-colors">
                  <span className={`text-lg flex-shrink-0 ${c.match ? "text-green-400" : "text-red-400"}`}>
                    {c.match ? "✓" : "✗"}
                  </span>
                  <span className="text-sm flex-1 truncate">{c.title_el}</span>
                </Link>
              ))}
            </div>
          </div>
        )}

        <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 text-xs text-gray-500 text-center">
          {el("CC BY 4.0 — Μόνο bills με ≥10 ψήφοι", "CC BY 4.0 — Only bills with ≥10 votes")}
        </div>
      </div>
    </main>
  );
}
