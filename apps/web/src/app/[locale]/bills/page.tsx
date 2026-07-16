"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { useLocale } from "next-intl";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ekklesia, municipal, Bill, BillQueryParams } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import RelevanceButtons from "@/components/RelevanceButtons";

type Periferia = { id: number; name_el: string };
type Dimos = { id: number; name_el: string };

const STATUS_FILTERS = [
  { key: "",                label_el: "Όλα",             label_en: "All" },
  { key: "ACTIVE",          label_el: "Ανοιχτά",         label_en: "Open" },
  { key: "WINDOW_24H",      label_el: "24ω",             label_en: "24h" },
  { key: "PARLIAMENT_VOTED",label_el: "Βουλή Αποφάσισε", label_en: "Voted" },
  { key: "OPEN_END",        label_el: "Αρχείο",          label_en: "Archive" },
];

const LEVEL_FILTERS = [
  { key: "",          label_el: "Όλα",        label_en: "All" },
  { key: "NATIONAL",  label_el: "Επικράτεια / Βουλή", label_en: "Nationwide / Parliament" },
  { key: "REGIONAL",  label_el: "Περιφέρεια", label_en: "Region" },
  { key: "MUNICIPAL", label_el: "Δήμος",      label_en: "Municipality" },
  { key: "DIAVGEIA",       label_el: "Διαύγεια",   label_en: "Diavgeia" },
  { key: "INSTITUTIONAL", label_el: "Φορείς",     label_en: "Institutions" },
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
  const [periferiaList, setPeriferiaList] = useState<Periferia[]>([]);
  const [dimosList, setDimosList] = useState<Dimos[]>([]);
  const [regionSearch, setRegionSearch] = useState("");
  const [dimosSearch, setDimosSearch] = useState("");
  const [selectedPeriferia, setSelectedPeriferia] = useState<number | null>(null);
  const [selectedPeriferiaName, setSelectedPeriferiaName] = useState("");
  const [selectedDimos, setSelectedDimos] = useState<number | null>(null);
  const [selectedDimosName, setSelectedDimosName] = useState("");
  const requestSequence = useRef(0);

  // Sync URL ?status= param on mount and navigation
  useEffect(() => {
    const urlStatus = searchParams.get("status") || "";
    if (urlStatus && urlStatus !== statusFilter) {
      setStatusFilter(urlStatus);
    }
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetch("https://api.ekklesia.gr/api/v1/periferia")
      .then(r => r.json()).then(setPeriferiaList).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedPeriferia === null) {
      setDimosList([]);
      setSelectedDimos(null);
      setSelectedDimosName("");
      setDimosSearch("");
      return;
    }

    municipal.dimoi(selectedPeriferia)
      .then(setDimosList)
      .catch(() => setDimosList([]));
  }, [selectedPeriferia]);

  useEffect(() => {
    if (levelFilter !== "REGIONAL" && levelFilter !== "MUNICIPAL") {
      setSelectedPeriferia(null);
      setSelectedPeriferiaName("");
      setRegionSearch("");
    }

    if (levelFilter !== "MUNICIPAL") {
      setSelectedDimos(null);
      setSelectedDimosName("");
      setDimosSearch("");
    }
  }, [levelFilter]);

  const billQueryParams: BillQueryParams = useMemo(() => {
    const params: BillQueryParams = {
      limit: PAGE_SIZE + 1,
      offset: (page - 1) * PAGE_SIZE,
      include_institutional: true,
    };

    if (statusFilter) {
      params.status = statusFilter;
    }

    if (search.trim()) {
      params.q = search.trim();
    }

    if (levelFilter === "NATIONAL") {
      params.governance = "NATIONAL";
    } else if (levelFilter === "REGIONAL") {
      params.governance = "REGIONAL";
      if (selectedPeriferia) params.periferia_id = selectedPeriferia;
    } else if (levelFilter === "MUNICIPAL") {
      params.governance = "MUNICIPAL";
      if (selectedDimos) {
        params.dimos_id = selectedDimos;
        if (selectedPeriferia) {
          params.periferia_id = selectedPeriferia;
        }
      }
    }

    if (levelFilter === "DIAVGEIA") {
      params.source = "DIAVGEIA";
    }

    if (levelFilter === "INSTITUTIONAL") {
      params.governance = "INSTITUTIONAL";
    }

    return params;
  }, [statusFilter, levelFilter, selectedPeriferia, selectedDimos, search, page]);

  useEffect(() => {
    const requestId = ++requestSequence.current;
    setLoading(true);
    ekklesia.getBills(billQueryParams)
      .then(r => {
        if (requestId !== requestSequence.current) return;
        setBills(r.data);
        setError(null);
      })
      .catch(() => {
        if (requestId === requestSequence.current) {
          setError(locale === "el" ? "Σφάλμα σύνδεσης API" : "API connection error");
        }
      })
      .finally(() => {
        if (requestId === requestSequence.current) setLoading(false);
      });
  }, [billQueryParams, locale]);

  const hasNextPage = bills.length > PAGE_SIZE;
  const paginated = bills.slice(0, PAGE_SIZE);

  // Reset page when filters change
  useEffect(() => { setPage(1); }, [statusFilter, levelFilter, search, selectedPeriferia, selectedDimos]);

  const titleKey = locale === "el" ? "title_el" : "title_en";
  const pillKey  = locale === "el" ? "pill_el"  : "pill_en";
  const shortKey = locale === "el" ? "summary_short_el" : "summary_short_en";
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

        {/* Region Typeahead */}
        <div className="mb-4 relative">
          {selectedPeriferia ? (
            <>
              <div className="flex items-center gap-2 px-4 py-2.5 bg-blue-50 border border-blue-300 rounded-xl text-sm">
                <span className="text-blue-700 font-semibold">📍 {selectedPeriferiaName}</span>
                <button
                  onClick={() => {
                    setSelectedPeriferia(null);
                    setSelectedPeriferiaName("");
                    setRegionSearch("");
                  }}
                  className="ml-auto text-blue-400 hover:text-blue-600 font-bold text-lg"
                >×</button>
              </div>
              <div className="mb-4 relative mt-3">
                {selectedDimos ? (
                  <div className="flex items-center gap-2 px-4 py-2.5 bg-blue-50 border border-blue-300 rounded-xl text-sm">
                    <span className="text-blue-700 font-semibold">🏘️ {selectedDimosName}</span>
                    <button
                      onClick={() => {
                        setSelectedDimos(null);
                        setSelectedDimosName("");
                        setDimosSearch("");
                        setLevelFilter("REGIONAL");
                      }}
                      className="ml-auto text-blue-400 hover:text-blue-600 font-bold text-lg"
                    >×</button>
                  </div>
                ) : (
                  <>
                    <input
                      type="text"
                      value={dimosSearch}
                      onChange={e => setDimosSearch(e.target.value)}
                      placeholder={isEl ? "🔍 Αναζήτηση Δήμου..." : "🔍 Search Municipality..."}
                      className="w-full px-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 transition-colors"
                    />
                    {dimosSearch.length >= 2 && (
                      <div className="absolute z-10 top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg max-h-48 overflow-y-auto">
                        {dimosList
                          .filter(dimos => dimos.name_el.toLowerCase().includes(dimosSearch.toLowerCase()))
                          .map(dimos => (
                            <button
                              key={dimos.id}
                              onClick={() => {
                                setSelectedDimos(dimos.id);
                                setSelectedDimosName(dimos.name_el);
                                setDimosSearch("");
                                setLevelFilter("MUNICIPAL");
                              }}
                              className="w-full text-left px-4 py-2.5 text-sm text-gray-700 hover:bg-blue-50 hover:text-blue-700 transition-colors"
                            >
                              🏘️ {dimos.name_el}
                            </button>
                          ))}
                        {dimosList
                          .filter(dimos => dimos.name_el.toLowerCase().includes(dimosSearch.toLowerCase()))
                          .length === 0 && (
                            <p className="px-4 py-2.5 text-sm text-gray-400">{isEl ? "Δεν βρέθηκε" : "Not found"}</p>
                          )}
                      </div>
                    )}
                  </>
                )}
              </div>
            </>
          ) : (
            <>
              <input
                type="text"
                value={regionSearch}
                onChange={e => setRegionSearch(e.target.value)}
                placeholder={isEl ? "🔍 Αναζήτηση Περιφέρειας..." : "🔍 Search Region..."}
                className="w-full px-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 transition-colors"
              />
              {regionSearch.length >= 2 && (
                <div className="absolute z-10 top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg max-h-48 overflow-y-auto">
                  {periferiaList
                    .filter(p => p.name_el.toLowerCase().includes(regionSearch.toLowerCase()))
                    .map(p => (
                      <button
                        key={p.id}
                        onClick={() => {
                          setSelectedPeriferia(p.id);
                          setSelectedPeriferiaName(p.name_el);
                          setLevelFilter("REGIONAL");
                          setRegionSearch("");
                          setSelectedDimos(null);
                          setSelectedDimosName("");
                        }}
                        className="w-full text-left px-4 py-2.5 text-sm text-gray-700 hover:bg-blue-50 hover:text-blue-700 transition-colors"
                      >
                        📍 {p.name_el}
                      </button>
                    ))}
                  {periferiaList.filter(p => p.name_el.toLowerCase().includes(regionSearch.toLowerCase())).length === 0 && (
                    <p className="px-4 py-2.5 text-sm text-gray-400">{isEl ? "Δεν βρέθηκε" : "Not found"}</p>
                  )}
                </div>
              )}
            </>
          )}
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
        {!loading && bills.length === 0 && !error && (
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
                <div className="flex items-center gap-2">
                  <StatusBadge status={bill.status} locale={locale} />
                  {(bill as any).source === "DIAVGEIA" && (
                    <span className="px-2 py-0.5 bg-sky-100 text-sky-700 text-xs font-bold rounded-md">
                      ΔΙΑΥΓΕΙΑ
                    </span>
                  )}
                </div>
                <span className="text-xs text-gray-400 font-mono">{bill.id}</span>
              </div>

              <h2 className="font-semibold text-lg text-gray-900 mb-2 group-hover:text-blue-700 transition-colors leading-snug">
                {bill[titleKey as keyof Bill] as string || bill.title_el}
              </h2>

              {(bill[shortKey as keyof Bill] || bill[pillKey as keyof Bill]) && (
                <p className="text-gray-500 text-sm leading-relaxed">
                  {(bill[shortKey as keyof Bill] || bill[pillKey as keyof Bill]) as string}
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

              {(bill as any).arweave_tx_id && (
                <a
                  href={`https://viewblock.io/arweave/tx/${(bill as any).arweave_tx_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="inline-flex items-center gap-1.5 mt-3 px-3 py-1.5 bg-purple-50 border border-purple-300 rounded-lg text-xs font-bold text-purple-700 hover:bg-purple-100 transition-colors"
                >
                  ⛓ Arweave: {(bill as any).arweave_tx_id.substring(0, 12)}…
                </a>
              )}

              {bill.status === "OPEN_END" && (bill as any).consensus_count > 0 && (
                <div className="mt-3 flex items-center gap-2 text-sm">
                  <span className="text-purple-600 font-bold">
                    ⚖️ {((bill as any).consensus_score || 0) > 0 ? "+" : ""}{((bill as any).consensus_score || 0).toFixed(1)}
                  </span>
                  <span className="text-gray-400 text-xs">
                    ({(bill as any).consensus_count} {isEl ? "αξιολογήσεις" : "ratings"})
                  </span>
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
        {!loading && (page > 1 || hasNextPage) && (
          <div className="flex items-center justify-between mt-8 bg-white rounded-xl p-4 border border-gray-200">
            <span className="text-sm text-gray-500">
              {isEl
                ? `Σελίδα ${page}`
                : `Page ${page}`}
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
                {page}
              </span>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={!hasNextPage}
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
          © 2026 V-Labs Development — MIT License —{" "}
          <a href="https://github.com/NeaBouli/pnyx" className="hover:text-gray-600" target="_blank">
            Open Source
          </a>
        </p>
      </footer>
    </main>
  );
}
