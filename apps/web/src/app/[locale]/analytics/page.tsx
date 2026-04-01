"use client";
import { useState, useEffect } from "react";
import { useLocale } from "next-intl";
import Link from "next/link";
import { analytics, exportUrls } from "@/lib/api";

export default function AnalyticsPage() {
  const locale = useLocale();
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const [overview, setOverview] = useState<any>(null);
  const [trends, setTrends]     = useState<any>(null);
  const [topDiv, setTopDiv]     = useState<any[]>([]);
  const [loading, setLoading]   = useState(true);
  const [days, setDays]         = useState(30);

  const el = (a: string, b: string) => locale === "el" ? a : b;

  useEffect(() => {
    Promise.all([
      analytics.overview(),
      analytics.trends(days),
      analytics.topDivergence(10),
    ]).then(([ov, tr, td]) => {
      setOverview(ov); setTrends(tr); setTopDiv(td?.data || []);
    }).finally(() => setLoading(false));
  }, [days]);

  if (loading) return (
    <main className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <div className="text-gray-400 animate-pulse">{el("Φόρτωση...", "Loading...")}</div>
    </main>
  );

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex justify-between items-center">
        <Link href="../bills" className="text-blue-400 font-bold">← εκκλησία</Link>
        <h1 className="text-sm font-bold text-gray-300">{el("Αναλυτικά Στοιχεία", "Analytics")}</h1>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-8">
        {/* Stats */}
        {overview && (
          <div className="grid grid-cols-3 gap-3 mb-8">
            <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 text-center">
              <div className="text-2xl font-black text-blue-400">{overview.votes?.total?.toLocaleString() ?? 0}</div>
              <div className="text-xs text-gray-500 mt-1">{el("Ψήφοι", "Votes")}</div>
            </div>
            <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 text-center">
              <div className="text-2xl font-black text-green-400">{overview.bills?.active ?? 0}</div>
              <div className="text-xs text-gray-500 mt-1">{el("Ενεργά", "Active")}</div>
            </div>
            <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 text-center">
              <div className="text-2xl font-black text-yellow-400">
                {overview.divergence?.average_score != null ? `${Math.round(overview.divergence.average_score * 100)}%` : "—"}
              </div>
              <div className="text-xs text-gray-500 mt-1">{el("Μέση Απόκλιση", "Avg Divergence")}</div>
            </div>
          </div>
        )}

        {/* Period */}
        <div className="flex gap-2 mb-6">
          {[7, 30, 90, 365].map(d => (
            <button key={d} onClick={() => setDays(d)}
              className={`px-4 py-2 rounded-lg text-sm font-bold transition-colors ${
                days === d ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"
              }`}>
              {d === 365 ? "1Y" : `${d}D`}
            </button>
          ))}
        </div>

        {/* Top Divergence */}
        {topDiv.length > 0 && (
          <>
            <h2 className="text-xl font-bold mb-4">{el("Υψηλότερη Απόκλιση", "Highest Divergence")}</h2>
            <div className="space-y-3 mb-8">
              {topDiv.map((item: any, i: number) => (
                <Link key={item.bill_id} href={`../bills/${item.bill_id}`}
                  className="block bg-gray-900 rounded-xl p-4 border border-gray-800 hover:border-blue-500 transition-all">
                  <div className="flex justify-between items-start gap-2">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <span className="text-gray-600 font-bold w-6 text-sm">#{i + 1}</span>
                      <p className="font-semibold text-sm truncate">{item.title_el}</p>
                    </div>
                    <span className={`text-xl font-black flex-shrink-0 ${
                      item.divergence_score > 0.4 ? "text-red-400" :
                      item.divergence_score > 0.2 ? "text-yellow-400" : "text-green-400"
                    }`}>{item.divergence_pct}%</span>
                  </div>
                  <div className="mt-2 h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${
                      item.divergence_score > 0.4 ? "bg-red-500" :
                      item.divergence_score > 0.2 ? "bg-yellow-500" : "bg-green-500"
                    }`} style={{ width: `${item.divergence_pct}%` }} />
                  </div>
                </Link>
              ))}
            </div>
          </>
        )}

        {/* By Category */}
        {trends?.by_category && Object.keys(trends.by_category).length > 0 && (
          <>
            <h2 className="text-xl font-bold mb-4">{el("Ανά Κατηγορία", "By Category")}</h2>
            <div className="space-y-2 mb-8">
              {Object.entries(trends.by_category)
                .sort((a: any, b: any) => b[1].avg_score - a[1].avg_score)
                .map(([cat, data]: any) => (
                  <div key={cat} className="bg-gray-900 rounded-xl p-3 border border-gray-800 flex items-center gap-3">
                    <span className="text-sm font-bold text-gray-300 flex-1">{cat}</span>
                    <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${
                        data.avg_score > 0.4 ? "bg-red-500" : data.avg_score > 0.2 ? "bg-yellow-500" : "bg-green-500"
                      }`} style={{ width: `${Math.round(data.avg_score * 100)}%` }} />
                    </div>
                    <span className="text-sm font-bold w-10 text-right">{Math.round(data.avg_score * 100)}%</span>
                  </div>
                ))}
            </div>
          </>
        )}

        {/* Export */}
        <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
          <h2 className="font-bold mb-4">{el("Εξαγωγή Δεδομένων", "Export Data")} — CC BY 4.0</h2>
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "Bills CSV", url: exportUrls.billsCsv },
              { label: "Results JSON", url: exportUrls.resultsJson },
              { label: "Divergence CSV", url: exportUrls.divergenceCsv },
            ].map(e => (
              <a key={e.label} href={e.url} target="_blank"
                className="flex items-center justify-center py-3 bg-gray-800 hover:bg-gray-700 rounded-xl text-sm font-semibold transition-colors">
                {e.label}
              </a>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
