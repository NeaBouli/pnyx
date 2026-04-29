"use client";

import { useState, useEffect, useMemo } from "react";
import { useLocale } from "next-intl";
import { useSearchParams } from "next/navigation";
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

const LEVEL_FILTERS = [
  { key: "",          label_el: "Όλα",        label_en: "All" },
  { key: "NATIONAL",  label_el: "Βουλή",      label_en: "Parliament" },
  { key: "REGIONAL",  label_el: "Περιφέρεια", label_en: "Region" },
  { key: "MUNICIPAL", label_el: "Δήμος",      label_en: "Municipality" },
];

const PAGE_SIZE = 10;

export default function BillsPage() {
  const locale = useLocale();
  const searchParams = useSearchParams();
  const [bills, setBills] = useState<Bill[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [levelFilter, setLevelFilter] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Sync URL ?status= param on mount and navigation
  useEffect(() => {
    const urlStatus = searchParams.get("status") || "";
    if (urlStatus && urlStatus !== statusFilter) {
      setStatusFilter(urlStatus);
    }
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setLoading(true);
    ekklesia.getBills(statusFilter || undefined)
      .then(r => { setBills(r.data); setError(null); })
      .catch(() => setError(locale === "el" ? "Σφάλμα σύνδεσης API" : "API connection error"))
      .finally(() => setLoading(false));
  }, [statusFilter, locale]);

  // Client-side filtering: search + governance level
  const filtered = useMemo(() => {
    let result = bills;
    if (levelFilter) {
      result = result.filter(b => (b as any).governance_level === levelFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(b =>
        (b.title_el?.toLowerCase().includes(q)) ||
        (b.title_en?.toLowerCase().includes(q)) ||
        (b.id?.toLowerCase().includes(q))
      );
    }
    return result;
  }, [bills, levelFilter, search]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Reset page when filters change
  useEffect(() => { setPage(1); }, [statusFilter, levelFilter, search]);

  const titleKey = locale === "el" ? "title_el" : "title_en";
  const pillKey  = locale === "el" ? "pill_el"  : "pill_en";
  const isEl = locale === "el";

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-6 py-10">
        {/* Header */}
        <div className="flex justify-between items-center mb-2">
          <h1 className="text-3xl font-black text-gray-900">
            {isEl ? "Νομοσχέδια" : "Parliament Bills"}
          </h1>
          <div className="flex gap-3 text-sm items-center">
            <Link href="results" className="text-xs text-gray-400 hover:text-blue-600 transition-colors">
              {isEl ? "Αποτελέσματα" : "Results"}
            </Link>
            <Link href="mp" className="text-xs text-gray-400 hover:text-blue-600 transition-colors">
              {isEl ? "Κόμματα" : "Parties"}
            </Link>
            <Link href="municipal" className="text-xs text-gray-400 hover:text-blue-600 transition-colors">
              {isEl ? "Δήμοι" : "Municipal"}
            </Link>
            <Link href="analytics" className="text-xs text-gray-400 hover:text-blue-600 transition-colors">
              Analytics
            </Link>
          </div>
        </div>
        <p className="text-gray-500 mb-6">
          {isEl
            ? "Ψηφίστε για πραγματικά κοινοβουλευτικά νομοσχέδια"
            : "Vote on real parliamentary bills"}
        </p>

        {/* Search */}
        <div className="mb-4">
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder={isEl ? "Αναζήτηση νομοσχεδίου..." : "Search bills..."}
            className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 transition-colors"
          />
        </div>

        {/* Governance Level Filter */}
        <div className="flex gap-2 mb-4 flex-wrap">
          {LEVEL_FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setLevelFilter(f.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                levelFilter === f.key
                  ? "bg-blue-100 text-blue-700 border border-blue-300"
                  : "bg-white text-gray-500 border border-gray-200 hover:border-gray-300 hover:text-gray-700"
              }`}
            >
              {isEl ? f.label_el : f.label_en}
            </button>
          ))}
        </div>

        {/* Status Filter Tabs */}
        <div className="flex gap-2 mb-8 flex-wrap">
          {STATUS_FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setStatusFilter(f.key)}
              className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
                statusFilter === f.key
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-white text-gray-500 hover:text-gray-900 border border-gray-200 hover:border-gray-300"
              }`}
            >
              {isEl ? f.label_el : f.label_en}
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
        {!loading && filtered.length === 0 && !error && (
          <div className="text-center py-16 text-gray-400">
            <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-4">
              🏛️
            </div>
            <p className="text-gray-600 font-medium">
              {isEl ? "Δεν βρέθηκαν νομοσχέδια" : "No bills found"}
            </p>
            {search && (
              <button onClick={() => setSearch("")} className="mt-2 text-blue-600 text-sm hover:underline">
                {isEl ? "Καθαρισμός αναζήτησης" : "Clear search"}
              </button>
            )}
          </div>
        )}

        {/* Bills List */}
        <div className="space-y-4">
          {paginated.map(bill => (
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
                  {isEl ? "Λεπτομέρειες →" : "Details →"}
                </span>
              </div>
            </Link>
          ))}
        </div>

        {/* Pagination */}
        {!loading && filtered.length > PAGE_SIZE && (
          <div className="flex items-center justify-between mt-8 bg-white rounded-xl p-4 border border-gray-200">
            <span className="text-sm text-gray-500">
              {isEl
                ? `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, filtered.length)} από ${filtered.length}`
                : `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, filtered.length)} of ${filtered.length}`}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="w-9 h-9 flex items-center justify-center rounded-lg border border-gray-200 text-gray-600 hover:border-blue-400 hover:text-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-bold"
              >
                ◀
              </button>
              <span className="flex items-center px-3 text-sm font-semibold text-gray-700">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="w-9 h-9 flex items-center justify-center rounded-lg border border-gray-200 text-gray-600 hover:border-blue-400 hover:text-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-bold"
              >
                ▶
              </button>
            </div>
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
