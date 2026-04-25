"use client";

import { useState, useEffect } from "react";
import { useLocale } from "next-intl";
import Link from "next/link";
import { ekklesia, Bill } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import RelevanceButtons from "@/components/RelevanceButtons";

const STATUS_FILTERS = [
  { key: "",                label_el: "Όλα",             label_en: "All" },
  { key: "ACTIVE",          label_el: "Ανοιχτά",         label_en: "Open" },
  { key: "WINDOW_24H",      label_el: "24ω",             label_en: "24h" },
  { key: "PARLIAMENT_VOTED",label_el: "Βουλή Αποφάσισε", label_en: "Voted" },
  { key: "OPEN_END",        label_el: "Αρχείο",          label_en: "Archive" },
];

export default function BillsPage() {
  const locale = useLocale();
  const [bills, setBills] = useState<Bill[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    ekklesia.getBills(filter || undefined)
      .then(r => { setBills(r.data); setError(null); })
      .catch(() => setError(locale === "el" ? "Σφάλμα σύνδεσης API" : "API connection error"))
      .finally(() => setLoading(false));
  }, [filter, locale]);

  const titleKey = locale === "el" ? "title_el" : "title_en";
  const pillKey  = locale === "el" ? "pill_el"  : "pill_en";

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-6 py-10">
        {/* Header */}
        <div className="flex justify-between items-center mb-2">
          <h1 className="text-3xl font-black text-gray-900">
            {locale === "el" ? "Νομοσχέδια" : "Parliament Bills"}
          </h1>
          <div className="flex gap-3 text-sm items-center">
            <Link href="results" className="text-xs text-gray-400 hover:text-blue-600 transition-colors">
              {locale === "el" ? "Αποτελέσματα" : "Results"}
            </Link>
            <Link href="analytics" className="text-xs text-gray-400 hover:text-blue-600 transition-colors">
              Analytics
            </Link>
          </div>
        </div>
        <p className="text-gray-500 mb-8">
          {locale === "el"
            ? "Ψηφίστε για πραγματικά κοινοβουλευτικά νομοσχέδια"
            : "Vote on real parliamentary bills"}
        </p>

        {/* Filter Tabs */}
        <div className="flex gap-2 mb-8 flex-wrap">
          {STATUS_FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
                filter === f.key
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-white text-gray-500 hover:text-gray-900 border border-gray-200 hover:border-gray-300"
              }`}
            >
              {locale === "el" ? f.label_el : f.label_en}
            </button>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="space-y-4">
            {[1,2,3].map(i => (
              <div key={i} className="bg-white rounded-2xl p-6 border border-gray-200 animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-3" />
                <div className="h-3 bg-gray-100 rounded w-1/2" />
              </div>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && bills.length === 0 && !error && (
          <div className="text-center py-16 text-gray-400">
            <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-4">
              🏛️
            </div>
            <p className="text-gray-600 font-medium">
              {locale === "el" ? "Δεν βρέθηκαν νομοσχέδια" : "No bills found"}
            </p>
            <p className="text-gray-400 text-sm mt-1">
              {locale === "el" ? "Σύντομα κοντά σας" : "Coming soon"}
            </p>
          </div>
        )}

        {/* Bills List */}
        <div className="space-y-4">
          {bills.map(bill => (
            <Link
              key={bill.id}
              href={`bills/${bill.id}`}
              className="block bg-white rounded-2xl p-6 border border-gray-200 hover:border-blue-400 hover:shadow-md transition-all group"
            >
              <div className="flex justify-between items-start gap-4 mb-3">
                <StatusBadge status={bill.status} locale={locale} />
                <span className="text-xs text-gray-400 font-mono">{bill.id}</span>
              </div>

              <h2 className="font-semibold text-lg text-gray-900 mb-2 group-hover:text-blue-700 transition-colors leading-snug">
                {bill[titleKey as keyof Bill] as string || bill.title_el}
              </h2>

              {bill[pillKey as keyof Bill] && (
                <p className="text-gray-500 text-sm leading-relaxed">
                  {bill[pillKey as keyof Bill] as string}
                </p>
              )}

              {bill.categories && (
                <div className="flex gap-2 mt-3 flex-wrap">
                  {bill.categories.map(cat => (
                    <span key={cat}
                      className="px-2 py-1 bg-gray-100 rounded-lg text-xs text-gray-500">
                      {cat}
                    </span>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between mt-4">
                <div onClick={(e) => e.preventDefault()}>
                  <RelevanceButtons billId={bill.id} initialScore={bill.relevance_score ?? 0} locale={locale} compact />
                </div>
                <span className="text-blue-600 text-sm font-semibold group-hover:text-blue-700">
                  {locale === "el" ? "Λεπτομέρειες →" : "Details →"}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-gray-200 px-6 py-6 text-center text-xs text-gray-400">
        <p>
          {locale === "el"
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
