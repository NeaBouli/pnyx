"use client";

import { useEffect, useMemo, useState } from "react";
import { useLocale } from "next-intl";
import Link from "next/link";
import PublicDataNav from "@/components/PublicDataNav";
import { ekklesia, type PublishedResult } from "@/lib/api";

type ResultFilter = "all" | "diverge" | "moderate" | "converge";

function scoreOf(result: PublishedResult): number | null {
  return typeof result.divergence_score === "number" ? result.divergence_score : null;
}

export default function ResultsPage() {
  const locale = useLocale();
  const isEl = locale === "el";
  const [data, setData] = useState<PublishedResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<ResultFilter>("all");
  const [sortBy, setSortBy] = useState<"divergence" | "votes">("votes");

  useEffect(() => {
    let active = true;
    ekklesia.getPublishedResults(1)
      .then((response) => {
        if (!active) return;
        setData(response.data.data);
        setError(null);
      })
      .catch(() => {
        if (active) setError(isEl ? "Αποτυχία φόρτωσης αποτελεσμάτων." : "Failed to load results.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [isEl]);

  const filtered = useMemo(() => data
    .filter((result) => {
      const score = scoreOf(result);
      if (filter === "all") return true;
      if (score === null) return false;
      if (filter === "diverge") return score > 0.4;
      if (filter === "moderate") return score > 0.2 && score <= 0.4;
      return score <= 0.2;
    })
    .sort((a, b) => {
      if (sortBy === "votes") return b.citizen_total - a.citizen_total;
      return (scoreOf(b) ?? -1) - (scoreOf(a) ?? -1);
    }), [data, filter, sortBy]);

  const totalVotes = data.reduce((sum, result) => sum + result.citizen_total, 0);
  const compared = data.filter((result) => scoreOf(result) !== null).length;
  const highDivergence = data.filter((result) => (scoreOf(result) ?? -1) > 0.4).length;
  const filters: Array<{ key: ResultFilter; el: string; en: string }> = [
    { key: "all", el: "Όλα", en: "All" },
    { key: "diverge", el: "Έντονη απόκλιση", en: "High divergence" },
    { key: "moderate", el: "Μέτρια", en: "Moderate" },
    { key: "converge", el: "Σύγκλιση", en: "Convergence" },
  ];

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-3xl px-6 py-8">
        <PublicDataNav />
        <div className="mb-6">
          <h1 className="text-3xl font-black text-gray-900">{isEl ? "Αποτελέσματα" : "Results"}</h1>
          <p className="mt-1 text-sm text-gray-500">
            {isEl ? "Συγκεντρωτικές, ανώνυμες ψήφοι πολιτών" : "Aggregated, anonymous citizen votes"}
          </p>
        </div>

        <div className="mb-8 grid grid-cols-3 gap-3">
          {[
            [totalVotes.toLocaleString(), isEl ? "Ψήφοι" : "Votes", "text-blue-600"],
            [data.length, isEl ? "Θέματα" : "Bills", "text-gray-800"],
            [highDivergence, isEl ? "Έντονη απόκλιση" : "High divergence", "text-red-700"],
          ].map(([value, label, color]) => (
            <div key={label} className="rounded-lg border border-gray-200 bg-white p-4 text-center">
              <div className={`text-2xl font-black ${color}`}>{value}</div>
              <div className="mt-1 text-xs text-gray-500">{label}</div>
            </div>
          ))}
        </div>

        <div className="mb-5 flex flex-wrap items-center gap-2">
          {filters.map((item) => (
            <button key={item.key} onClick={() => setFilter(item.key)}
              className={`rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${filter === item.key ? "bg-blue-600 text-white" : "border border-gray-200 bg-white text-gray-500 hover:text-gray-900"}`}>
              {isEl ? item.el : item.en}
            </button>
          ))}
          <select value={sortBy} onChange={(event) => setSortBy(event.target.value as typeof sortBy)}
            aria-label={isEl ? "Ταξινόμηση" : "Sort results"}
            className="ml-auto rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700">
            <option value="votes">{isEl ? "Περισσότερες ψήφοι" : "Most votes"}</option>
            <option value="divergence">{isEl ? "Μεγαλύτερη απόκλιση" : "Highest divergence"}</option>
          </select>
        </div>

        {loading && <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-gray-400">{isEl ? "Φόρτωση..." : "Loading..."}</div>}
        {!loading && error && <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
        {!loading && !error && filtered.length === 0 && (
          <div className="rounded-lg border border-gray-200 bg-white p-10 text-center text-gray-500">
            {filter === "all" ? (isEl ? "Δεν υπάρχουν αποτελέσματα ακόμα." : "No results yet.") : (isEl ? "Δεν υπάρχουν αποτελέσματα σε αυτή την κατηγορία." : "No results in this category.")}
          </div>
        )}

        <div className="space-y-3">
          {filtered.map((result) => {
            const score = scoreOf(result);
            const title = !isEl && result.title_en ? result.title_en : result.title_el;
            return (
              <Link key={result.bill_id} href={`/${locale}/bills/${result.bill_id}`}
                className="block rounded-lg border border-gray-200 bg-white p-5 transition-colors hover:border-blue-400">
                <div className="flex items-start justify-between gap-4">
                  <h2 className="font-bold leading-snug text-gray-900">{title}</h2>
                  <span className="shrink-0 text-sm font-bold text-blue-700">{result.citizen_total} {isEl ? "ψήφοι" : "votes"}</span>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
                  <div><span className="text-gray-500">{isEl ? "Υπέρ" : "Yes"}</span><strong className="ml-2 text-green-700">{result.yes_pct}%</strong></div>
                  <div><span className="text-gray-500">{isEl ? "Κατά" : "No"}</span><strong className="ml-2 text-red-700">{result.no_pct}%</strong></div>
                  <div><span className="text-gray-500">{isEl ? "Αποχή" : "Abstain"}</span><strong className="ml-2 text-gray-700">{result.abstain_pct}%</strong></div>
                </div>
                <p className="mt-3 text-xs text-gray-500">
                  {score === null ? (isEl ? "Δεν υπάρχει ακόμη κοινοβουλευτικό αποτέλεσμα για σύγκριση." : "No parliamentary result is available for comparison yet.") : `${isEl ? "Απόκλιση" : "Divergence"}: ${Math.round(score * 100)}%`}
                </p>
              </Link>
            );
          })}
        </div>

        {!loading && !error && data.length > 0 && (
          <div className="mt-8 rounded-lg border border-blue-200 bg-blue-50 p-4 text-xs leading-relaxed text-gray-600">
            {isEl ? `Η απόκλιση εμφανίζεται μόνο όταν υπάρχει επίσημο κοινοβουλευτικό αποτέλεσμα (${compared} από ${data.length} θέματα).` : `Divergence is shown only when an official parliamentary result exists (${compared} of ${data.length} bills).`}
          </div>
        )}
      </div>
      <footer className="border-t border-gray-200 px-6 py-6 text-center text-xs text-gray-400">
        <p>{isEl ? "Μη κρατική εφαρμογή — ενημερωτικός χαρακτήρας" : "Non-governmental application — informational purposes only"}</p>
        <p className="mt-1">
          © 2026 V-Labs Development — MIT License —{" "}
          <a href="https://github.com/NeaBouli/pnyx" className="hover:text-gray-600" target="_blank" rel="noreferrer">Open Source</a>
        </p>
      </footer>
    </main>
  );
}
