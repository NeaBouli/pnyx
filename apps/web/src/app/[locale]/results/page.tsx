"use client";

import { useState, useEffect } from "react";
import { useLocale } from "next-intl";
import Link from "next/link";
import { ekklesia, Bill, BillResults } from "@/lib/api";

type BillWithResults = {
  bill: Bill;
  results: BillResults | null;
};

export default function ResultsPage() {
  const locale = useLocale();
  const [data, setData] = useState<BillWithResults[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "diverge" | "converge">("all");
  const [sortBy, setSortBy] = useState<"divergence" | "votes">("divergence");

  useEffect(() => {
    async function load() {
      try {
        const billsRes = await ekklesia.getBills();
        const bills: Bill[] = billsRes.data;
        const withResults = await Promise.all(
          bills.map(async (bill) => {
            try {
              const r = await ekklesia.getResults(bill.id);
              return { bill, results: r.data };
            } catch {
              return { bill, results: null };
            }
          })
        );
        setData(withResults.filter(d => d.results && d.results.total_votes > 0));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filtered = data
    .filter(d => {
      if (!d.results?.divergence) return filter === "all";
      const score = d.results.divergence.score * 100;
      if (filter === "diverge")  return score > 40;
      if (filter === "converge") return score <= 20;
      return true;
    })
    .sort((a, b) => {
      if (sortBy === "votes") {
        return (b.results?.total_votes ?? 0) - (a.results?.total_votes ?? 0);
      }
      const da = (a.results?.divergence?.score ?? 0);
      const db = (b.results?.divergence?.score ?? 0);
      return db - da;
    });

  function divergenceColor(score: number) {
    if (score > 0.4) return { bg: "bg-red-950",    border: "border-red-800",    text: "text-red-400",    bar: "bg-red-500" };
    if (score > 0.2) return { bg: "bg-yellow-950", border: "border-yellow-800", text: "text-yellow-400", bar: "bg-yellow-500" };
    return              { bg: "bg-green-950",   border: "border-green-800",  text: "text-green-400",  bar: "bg-green-500" };
  }

  function divergenceLabel(score: number) {
    if (locale === "el") {
      if (score > 0.4) return "Έντονη Απόκλιση";
      if (score > 0.2) return "Μέτρια Απόκλιση";
      return "Σύγκλιση";
    }
    if (score > 0.4) return "High Divergence";
    if (score > 0.2) return "Moderate Divergence";
    return "Convergence";
  }

  const totalVotes   = data.reduce((s, d) => s + (d.results?.total_votes ?? 0), 0);
  const highDiverge  = data.filter(d => (d.results?.divergence?.score ?? 0) > 0.4).length;
  const converge     = data.filter(d => (d.results?.divergence?.score ?? 0) <= 0.2).length;

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex justify-between items-center">
        <Link href="../bills" className="text-blue-400 font-bold">← εκκλησία</Link>
        <h1 className="text-sm font-bold text-gray-300">
          {locale === "el" ? "Αποτελέσματα & Απόκλιση" : "Results & Divergence"}
        </h1>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-8">

        {/* Stats Banner */}
        <div className="grid grid-cols-3 gap-3 mb-8">
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 text-center">
            <div className="text-2xl font-black text-blue-400">
              {totalVotes.toLocaleString()}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {locale === "el" ? "Συνολικές Ψήφοι" : "Total Votes"}
            </div>
          </div>
          <div className="bg-red-950 rounded-xl p-4 border border-red-900 text-center">
            <div className="text-2xl font-black text-red-400">{highDiverge}</div>
            <div className="text-xs text-gray-500 mt-1">
              {locale === "el" ? "Έντονη Απόκλιση" : "High Divergence"}
            </div>
          </div>
          <div className="bg-green-950 rounded-xl p-4 border border-green-900 text-center">
            <div className="text-2xl font-black text-green-400">{converge}</div>
            <div className="text-xs text-gray-500 mt-1">
              {locale === "el" ? "Σύγκλιση" : "Convergence"}
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex gap-2 mb-4 flex-wrap">
          {[
            { key: "all",      el: "Όλα",         en: "All" },
            { key: "diverge",  el: "Απόκλιση",    en: "Divergence" },
            { key: "converge", el: "Σύγκλιση",    en: "Convergence" },
          ].map(f => (
            <button key={f.key}
              onClick={() => setFilter(f.key as typeof filter)}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                filter === f.key
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              {locale === "el" ? f.el : f.en}
            </button>
          ))}
          <div className="ml-auto flex gap-2">
            {[
              { key: "divergence", el: "Απόκλιση ↓", en: "Divergence ↓" },
              { key: "votes",      el: "Ψήφοι ↓",    en: "Votes ↓" },
            ].map(s => (
              <button key={s.key}
                onClick={() => setSortBy(s.key as typeof sortBy)}
                className={`px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${
                  sortBy === s.key
                    ? "bg-gray-700 text-white"
                    : "bg-gray-900 text-gray-500 hover:text-white"
                }`}
              >
                {locale === "el" ? s.el : s.en}
              </button>
            ))}
          </div>
        </div>

        {/* Loading */}
        {loading && (
          <div className="space-y-3">
            {[1,2,3].map(i => (
              <div key={i} className="h-32 bg-gray-900 rounded-2xl animate-pulse border border-gray-800"/>
            ))}
          </div>
        )}

        {/* Empty */}
        {!loading && filtered.length === 0 && (
          <div className="text-center py-20 text-gray-500">
            {locale === "el" ? "Δεν υπάρχουν αποτελέσματα ακόμα." : "No results yet."}
          </div>
        )}

        {/* Cards */}
        <div className="space-y-4">
          {filtered.map(({ bill, results }) => {
            if (!results) return null;
            const score = results.divergence?.score ?? 0;
            const c = divergenceColor(score);
            const titleKey = locale === "el" ? "title_el" : "title_en";

            return (
              <Link key={bill.id} href={`../bills/${bill.id}`}
                className={`block rounded-2xl p-5 border ${c.bg} ${c.border} hover:ring-1 hover:ring-blue-500 transition-all`}
              >
                {/* Header */}
                <div className="flex justify-between items-start mb-3 gap-2">
                  <h3 className="font-bold text-sm leading-snug flex-1">
                    {(titleKey === "title_en" && bill.title_en) ? bill.title_en : bill.title_el}
                  </h3>
                  <div className="text-right flex-shrink-0">
                    <div className={`text-2xl font-black ${c.text}`}>
                      {Math.round(score * 100)}%
                    </div>
                    <div className={`text-xs ${c.text}`}>
                      {divergenceLabel(score)}
                    </div>
                  </div>
                </div>

                {/* Divergence Bar */}
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden mb-3">
                  <div
                    className={`h-full ${c.bar} rounded-full transition-all duration-700`}
                    style={{ width: `${Math.round(score * 100)}%` }}
                  />
                </div>

                {/* Vote Bars */}
                <div className="grid grid-cols-3 gap-2 mb-3">
                  {[
                    { label: locale === "el" ? "Υπέρ" : "Yes",     pct: results.yes_percent,     color: "bg-green-600" },
                    { label: locale === "el" ? "Κατά" : "No",      pct: results.no_percent,      color: "bg-red-600" },
                    { label: locale === "el" ? "Αποχή" : "Abstain",pct: results.abstain_percent, color: "bg-gray-600" },
                  ].map(bar => (
                    <div key={bar.label}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-gray-400">{bar.label}</span>
                        <span className="font-bold">{bar.pct}%</span>
                      </div>
                      <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <div className={`h-full ${bar.color} rounded-full`}
                          style={{ width: `${bar.pct}%` }} />
                      </div>
                    </div>
                  ))}
                </div>

                {/* Headline + Meta */}
                <div className="flex justify-between items-center">
                  {results.divergence?.headline_el && (
                    <p className={`text-xs ${c.text} flex-1`}>
                      {results.divergence.headline_el}
                    </p>
                  )}
                  <span className="text-xs text-gray-600 ml-2 flex-shrink-0">
                    {results.total_votes.toLocaleString()}{" "}
                    {locale === "el" ? "ψήφοι" : "votes"}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>

        {/* Info Box */}
        {!loading && filtered.length > 0 && (
          <div className="mt-8 bg-gray-900 rounded-xl p-4 border border-gray-800 text-xs text-gray-500 leading-relaxed">
            <strong className="text-gray-400">
              {locale === "el" ? "Δείκτης Απόκλισης:" : "Divergence Score:"}
            </strong>{" "}
            {locale === "el"
              ? "Μετρά τη διαφορά μεταξύ της πλειοψηφίας των πολιτών και της απόφασης της Βουλής. 0% = πλήρης σύγκλιση, 100% = πλήρης αντίθεση."
              : "Measures the gap between citizen majority and parliamentary decision. 0% = full convergence, 100% = full opposition."}
          </div>
        )}
      </div>

      <footer className="border-t border-gray-800 px-6 py-6 text-center text-xs text-gray-600">
        © 2026 Vendetta Labs — MIT —{" "}
        <a href="https://github.com/NeaBouli/pnyx" target="_blank" className="hover:text-gray-400">
          Open Source
        </a>
      </footer>
    </main>
  );
}
