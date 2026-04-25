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
  const isEl = locale === "el";
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
    if (score > 0.4) return { bg: "bg-red-50",    border: "border-red-200",    text: "text-red-700",    bar: "bg-red-500",    statBg: "bg-red-50",  statBorder: "border-red-200",  statText: "text-red-700" };
    if (score > 0.2) return { bg: "bg-yellow-50", border: "border-yellow-200", text: "text-yellow-700", bar: "bg-yellow-500", statBg: "bg-yellow-50", statBorder: "border-yellow-200", statText: "text-yellow-700" };
    return              { bg: "bg-green-50",   border: "border-green-200",  text: "text-green-700",  bar: "bg-green-500",  statBg: "bg-green-50", statBorder: "border-green-200", statText: "text-green-700" };
  }

  function divergenceLabel(score: number) {
    if (isEl) {
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
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-6 py-8">
        <div className="flex justify-between items-center mb-6">
          <Link href="bills" className="text-blue-600 text-sm hover:text-blue-700 font-medium">
            ← {isEl ? "Νομοσχέδια" : "Bills"}
          </Link>
          <h1 className="text-sm font-bold text-gray-600">
            {isEl ? "Αποτελέσματα & Απόκλιση" : "Results & Divergence"}
          </h1>
        </div>

        {/* Stats Banner */}
        <div className="grid grid-cols-3 gap-3 mb-8">
          <div className="bg-white rounded-xl p-4 border border-gray-200 text-center">
            <div className="text-2xl font-black text-blue-600">
              {totalVotes.toLocaleString()}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {isEl ? "Συνολικές Ψήφοι" : "Total Votes"}
            </div>
          </div>
          <div className="bg-red-50 rounded-xl p-4 border border-red-200 text-center">
            <div className="text-2xl font-black text-red-700">{highDiverge}</div>
            <div className="text-xs text-gray-500 mt-1">
              {isEl ? "Έντονη Απόκλιση" : "High Divergence"}
            </div>
          </div>
          <div className="bg-green-50 rounded-xl p-4 border border-green-200 text-center">
            <div className="text-2xl font-black text-green-700">{converge}</div>
            <div className="text-xs text-gray-500 mt-1">
              {isEl ? "Σύγκλιση" : "Convergence"}
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
                  : "bg-white text-gray-500 border border-gray-200 hover:text-gray-900"
              }`}
            >
              {isEl ? f.el : f.en}
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
                    ? "bg-gray-200 text-gray-900"
                    : "bg-white text-gray-400 border border-gray-200 hover:text-gray-700"
                }`}
              >
                {isEl ? s.el : s.en}
              </button>
            ))}
          </div>
        </div>

        {/* Loading */}
        {loading && (
          <div className="space-y-3">
            {[1,2,3].map(i => (
              <div key={i} className="h-32 bg-white rounded-2xl animate-pulse border border-gray-200"/>
            ))}
          </div>
        )}

        {/* Empty */}
        {!loading && filtered.length === 0 && (
          <div className="text-center py-20 text-gray-500">
            {isEl ? "Δεν υπάρχουν αποτελέσματα ακόμα." : "No results yet."}
          </div>
        )}

        {/* Cards */}
        <div className="space-y-4">
          {filtered.map(({ bill, results }) => {
            if (!results) return null;
            const score = results.divergence?.score ?? 0;
            const c = divergenceColor(score);
            const tk = isEl ? "title_el" : "title_en";

            return (
              <Link key={bill.id} href={`bills/${bill.id}`}
                className={`block rounded-2xl p-5 border ${c.bg} ${c.border} hover:shadow-md transition-all`}
              >
                {/* Header */}
                <div className="flex justify-between items-start mb-3 gap-2">
                  <h3 className="font-bold text-sm text-gray-900 leading-snug flex-1">
                    {(tk === "title_en" && bill.title_en) ? bill.title_en : bill.title_el}
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
                <div className="h-2 bg-gray-200 rounded-full overflow-hidden mb-3">
                  <div
                    className={`h-full ${c.bar} rounded-full transition-all duration-700`}
                    style={{ width: `${Math.round(score * 100)}%` }}
                  />
                </div>

                {/* Vote Bars */}
                <div className="grid grid-cols-3 gap-2 mb-3">
                  {[
                    { label: isEl ? "Υπέρ" : "Yes",     pct: results.yes_percent,     color: "bg-green-500" },
                    { label: isEl ? "Κατά" : "No",      pct: results.no_percent,      color: "bg-red-500" },
                    { label: isEl ? "Αποχή" : "Abstain",pct: results.abstain_percent, color: "bg-gray-400" },
                  ].map(bar => (
                    <div key={bar.label}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-gray-500">{bar.label}</span>
                        <span className="font-bold text-gray-700">{bar.pct}%</span>
                      </div>
                      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
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
                  <span className="text-xs text-gray-400 ml-2 flex-shrink-0">
                    {results.total_votes.toLocaleString()}{" "}
                    {isEl ? "ψήφοι" : "votes"}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>

        {/* Info Box */}
        {!loading && filtered.length > 0 && (
          <div className="mt-8 bg-blue-50 rounded-xl p-4 border border-blue-200 text-xs text-gray-600 leading-relaxed">
            <strong className="text-gray-700">
              {isEl ? "Δείκτης Απόκλισης:" : "Divergence Score:"}
            </strong>{" "}
            {isEl
              ? "Μετρά τη διαφορά μεταξύ της πλειοψηφίας των πολιτών και της απόφασης της Βουλής. 0% = πλήρης σύγκλιση, 100% = πλήρης αντίθεση."
              : "Measures the gap between citizen majority and parliamentary decision. 0% = full convergence, 100% = full opposition."}
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="border-t border-gray-200 px-6 py-6 text-center text-xs text-gray-400">
        <p>
          {isEl
            ? "Μη κρατική εφαρμογή — ενημερωτικός χαρακτήρας"
            : "Non-governmental application — informational purposes only"}
        </p>
        <p className="mt-1">
          © 2026 Vendetta Labs — MIT License —{" "}
          <a href="https://github.com/NeaBouli/pnyx" className="hover:text-gray-600" target="_blank">
            Open Source
          </a>
        </p>
      </footer>
    </main>
  );
}
