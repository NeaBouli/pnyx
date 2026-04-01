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
      .catch(() => setError("API nicht erreichbar"))
      .finally(() => setLoading(false));
  }, [filter]);

  const titleKey = locale === "el" ? "title_el" : "title_en";
  const pillKey  = locale === "el" ? "pill_el"  : "pill_en";

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex justify-between items-center">
        <Link href=".." className="text-blue-400 font-bold text-xl">← εκκλησία</Link>
        <div className="flex gap-3 text-sm text-gray-400 items-center">
          <Link href="results" className="text-xs text-gray-500 hover:text-blue-400 transition-colors">
            {locale === "el" ? "Αποτελέσματα" : "Results"}
          </Link>
          <Link href="/el/bills" className="hover:text-white">ΕΛ</Link>
          <Link href="/en/bills" className="hover:text-white">EN</Link>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-10">
        <h1 className="text-3xl font-bold mb-2">
          🏛️ {locale === "el" ? "Νομοσχέδια" : "Parliament Bills"}
        </h1>
        <p className="text-gray-400 mb-8">
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
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              {locale === "el" ? f.label_el : f.label_en}
            </button>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-900/50 border border-red-700 rounded-xl p-4 mb-6 text-red-300 text-sm">
            {error} — Backend läuft? <code>cd apps/api && uvicorn main:app</code>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="space-y-4">
            {[1,2,3].map(i => (
              <div key={i} className="bg-gray-900 rounded-2xl p-6 border border-gray-800 animate-pulse">
                <div className="h-4 bg-gray-700 rounded w-3/4 mb-3" />
                <div className="h-3 bg-gray-800 rounded w-1/2" />
              </div>
            ))}
          </div>
        )}

        {/* Bills Liste */}
        {!loading && bills.length === 0 && !error && (
          <div className="text-center py-16 text-gray-500">
            <p className="text-5xl mb-4">🏛️</p>
            <p>{locale === "el" ? "Δεν βρέθηκαν νομοσχέδια" : "No bills found"}</p>
          </div>
        )}

        <div className="space-y-4">
          {bills.map(bill => (
            <Link
              key={bill.id}
              href={`bills/${bill.id}`}
              className="block bg-gray-900 rounded-2xl p-6 border border-gray-800 hover:border-blue-700 transition-all group"
            >
              <div className="flex justify-between items-start gap-4 mb-3">
                <StatusBadge status={bill.status} locale={locale} />
                <span className="text-xs text-gray-600 font-mono">{bill.id}</span>
              </div>

              <h2 className="font-semibold text-lg mb-2 group-hover:text-blue-400 transition-colors leading-snug">
                {bill[titleKey as keyof Bill] as string || bill.title_el}
              </h2>

              {bill[pillKey as keyof Bill] && (
                <p className="text-gray-400 text-sm leading-relaxed">
                  {bill[pillKey as keyof Bill] as string}
                </p>
              )}

              {bill.categories && (
                <div className="flex gap-2 mt-3 flex-wrap">
                  {bill.categories.map(cat => (
                    <span key={cat}
                      className="px-2 py-1 bg-gray-800 rounded-lg text-xs text-gray-400">
                      {cat}
                    </span>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between mt-4">
                <div onClick={(e) => e.preventDefault()}>
                  <RelevanceButtons billId={bill.id} initialScore={bill.relevance_score ?? 0} locale={locale} compact />
                </div>
                <span className="text-blue-400 text-sm font-semibold group-hover:text-blue-300">
                  {locale === "el" ? "Ψηφίστε →" : "Vote →"}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>

      <footer className="border-t border-gray-800 px-6 py-6 text-center text-xs text-gray-600">
        © 2026 Vendetta Labs — MIT License —{" "}
        <a href="https://github.com/NeaBouli/pnyx" className="hover:text-gray-400" target="_blank">
          Open Source
        </a>
      </footer>
    </main>
  );
}
