"use client";

import { useState, useEffect } from "react";
import { useLocale } from "next-intl";
import Link from "next/link";
import { ekklesia, Bill, BillResults } from "@/lib/api";
import { loadKeypair, loadNullifier, signVote } from "@/lib/crypto";
import StatusBadge from "@/components/StatusBadge";
import RelevanceButtons from "@/components/RelevanceButtons";
import DivergenceCard from "@/components/DivergenceCard";

const VOTE_OPTIONS = [
  { value: "YES",     label_el: "Υπέρ",               label_en: "Yes",            color: "bg-green-700 hover:bg-green-600 border-green-600" },
  { value: "NO",      label_el: "Κατά",               label_en: "No",             color: "bg-red-700 hover:bg-red-600 border-red-600" },
  { value: "ABSTAIN", label_el: "Αποχή",              label_en: "Abstain",        color: "bg-gray-700 hover:bg-gray-600 border-gray-600" },
  { value: "UNKNOWN", label_el: "Δεν γνωρίζω αρκετά", label_en: "Don't know enough", color: "bg-yellow-800 hover:bg-yellow-700 border-yellow-700" },
];

const VOTABLE = ["ACTIVE", "WINDOW_24H", "OPEN_END"];

export default function BillDetailPage({ params }: { params: { id: string } }) {
  const locale = useLocale();
  const billId = decodeURIComponent(params.id);

  const [bill, setBill]         = useState<Bill | null>(null);
  const [results, setResults]   = useState<BillResults | null>(null);
  const [loading, setLoading]   = useState(true);
  const [expanded, setExpanded] = useState<"short" | "long">("short");
  const [voteStatus, setVoteStatus] = useState<"idle" | "needs_key" | "voted" | "already" | "invalid_sig" | "error">("idle");
  const [selectedVote, setSelectedVote] = useState<string | null>(null);
  const [voteLoading, setVoteLoading] = useState(false);
  const [voteError, setVoteError] = useState<string | null>(null);

  const titleKey = locale === "el" ? "title_el" : "title_en";
  const shortKey = locale === "el" ? "summary_short_el" : "summary_short_en";

  useEffect(() => {
    Promise.all([
      ekklesia.getBill(billId),
      ekklesia.getResults(billId),
    ]).then(([billRes, resultsRes]) => {
      setBill(billRes.data);
      setResults(resultsRes.data);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [billId]);

  async function handleVoteClick(choice: string) {
    // 1. Check keypair
    const keypair = loadKeypair();
    const nullifier = loadNullifier();

    if (!keypair || !nullifier) {
      // Save current path so verify page can redirect back
      sessionStorage.setItem("verify_redirect", window.location.pathname);
      setVoteStatus("needs_key");
      setSelectedVote(choice);
      return;
    }

    // 2. Sign vote with Ed25519
    setVoteLoading(true);
    setVoteError(null);
    setSelectedVote(choice);

    try {
      const signatureHex = signVote(keypair.privateKeyHex, {
        bill_id: billId,
        vote: choice,
        nullifier_hash: nullifier,
      });

      // 3. POST to API
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API_URL}/api/v1/vote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nullifier_hash: nullifier,
          bill_id: billId,
          vote: choice,
          signature_hex: signatureHex,
        }),
      });

      if (res.ok) {
        setVoteStatus("voted");
        // 4. Refresh results
        try {
          const resultsRes = await ekklesia.getResults(billId);
          setResults(resultsRes.data);
        } catch { /* results refresh optional */ }
      } else if (res.status === 409) {
        setVoteStatus("already");
      } else if (res.status === 401) {
        setVoteStatus("invalid_sig");
      } else {
        const err = await res.json().catch(() => ({}));
        setVoteError(err.detail || `Error ${res.status}`);
        setVoteStatus("error");
      }
    } catch (err) {
      setVoteError(err instanceof Error ? err.message : "Network error");
      setVoteStatus("error");
    } finally {
      setVoteLoading(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <div className="text-gray-400 animate-pulse">
          {locale === "el" ? "Φόρτωση..." : "Loading..."}
        </div>
      </main>
    );
  }

  if (!bill) {
    return (
      <main className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <div className="text-center">
          <p className="text-5xl mb-4">🏛️</p>
          <p className="text-gray-400">
            {locale === "el" ? "Νομοσχέδιο δεν βρέθηκε" : "Bill not found"}
          </p>
          <Link href="../bills" className="mt-4 inline-block text-blue-400 hover:text-blue-300">
            ← {locale === "el" ? "Πίσω" : "Back"}
          </Link>
        </div>
      </main>
    );
  }

  const canVote = VOTABLE.includes(bill.status);

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex justify-between items-center">
        <Link href="../bills" className="text-blue-400 font-bold">← εκκλησία</Link>
        <div className="flex gap-3 text-sm text-gray-400">
          <Link href={`/el/bills/${billId}`} className="hover:text-white">ΕΛ</Link>
          <Link href={`/en/bills/${billId}`} className="hover:text-white">EN</Link>
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-10">
        {/* Status + ID */}
        <div className="flex justify-between items-center mb-4">
          <StatusBadge status={bill.status} locale={locale} />
          <span className="text-xs text-gray-600 font-mono">{bill.id}</span>
        </div>

        {/* Relevance */}
        <div className="flex items-center gap-3 mb-4">
          <span className="text-sm text-gray-500">
            {locale === "el" ? "Σημαντικότητα:" : "Importance:"}
          </span>
          <RelevanceButtons billId={billId} locale={locale} />
        </div>

        {/* Titel */}
        <h1 className="text-2xl font-bold leading-snug mb-6">
          {bill[titleKey as keyof Bill] as string || bill.title_el}
        </h1>

        {/* Kategorien */}
        {bill.categories && (
          <div className="flex gap-2 mb-6 flex-wrap">
            {bill.categories.map(cat => (
              <span key={cat} className="px-3 py-1 bg-gray-800 rounded-lg text-xs text-gray-400">
                {cat}
              </span>
            ))}
          </div>
        )}

        {/* Zusammenfassung */}
        <div className="bg-gray-900 rounded-2xl p-6 mb-6 border border-gray-800">
          <div className="flex gap-3 mb-4">
            {["short", "long"].map(level => (
              <button
                key={level}
                onClick={() => setExpanded(level as "short" | "long")}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  expanded === level
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-white"
                }`}
              >
                {level === "short"
                  ? (locale === "el" ? "Σύνοψη" : "Summary")
                  : (locale === "el" ? "Ανάλυση" : "Analysis")}
              </button>
            ))}
          </div>
          <p className="text-gray-300 leading-relaxed">
            {expanded === "short"
              ? (bill[shortKey as keyof Bill] as string || bill.pill_el || "—")
              : (locale === "el" ? bill.summary_long_el : bill.summary_long_en) || "—"
            }
          </p>
        </div>

        {/* ── ABSTIMMUNG ── */}
        {canVote && (
          <div className="bg-gray-900 rounded-2xl p-6 mb-6 border border-gray-800">
            <h2 className="font-bold text-lg mb-4">
              🗳️ {locale === "el" ? "Η ψήφος σας" : "Your vote"}
            </h2>

            <div className="grid grid-cols-2 gap-3 mb-4">
              {VOTE_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => handleVoteClick(opt.value)}
                  disabled={voteLoading || voteStatus === "voted"}
                  className={`py-4 px-4 rounded-xl font-semibold border-2 transition-all ${opt.color} ${
                    selectedVote === opt.value
                      ? "ring-2 ring-white scale-105"
                      : "opacity-80"
                  } ${(voteLoading || voteStatus === "voted") ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  {voteLoading && selectedVote === opt.value
                    ? (locale === "el" ? "Υπογραφή..." : "Signing...")
                    : (locale === "el" ? opt.label_el : opt.label_en)}
                </button>
              ))}
            </div>

            {/* Vote Status Messages */}
            {voteStatus === "needs_key" && (
              <div className="bg-yellow-900/50 border border-yellow-700 rounded-xl p-4 text-yellow-300 text-sm">
                <p className="font-semibold mb-2">
                  {locale === "el"
                    ? "Απαιτείται επαλήθευση ταυτότητας"
                    : "Identity verification required"}
                </p>
                <Link
                  href="../verify"
                  className="inline-block px-4 py-2 bg-yellow-700 hover:bg-yellow-600 rounded-lg font-semibold transition-colors"
                >
                  {locale === "el" ? "Επαλήθευση →" : "Verify →"}
                </Link>
              </div>
            )}

            {voteStatus === "voted" && (
              <div className="bg-green-900/50 border border-green-700 rounded-xl p-4 text-green-300 text-sm">
                ✓ {locale === "el"
                  ? `Ψήφος "${selectedVote}" καταγράφηκε με Ed25519 υπογραφή.`
                  : `Vote "${selectedVote}" recorded with Ed25519 signature.`}
              </div>
            )}

            {voteStatus === "already" && (
              <div className="bg-yellow-900/50 border border-yellow-700 rounded-xl p-4 text-yellow-300 text-sm">
                {locale === "el"
                  ? "Έχετε ήδη ψηφίσει για αυτό το νομοσχέδιο."
                  : "You have already voted on this bill."}
              </div>
            )}

            {voteStatus === "invalid_sig" && (
              <div className="bg-red-900/50 border border-red-700 rounded-xl p-4 text-red-300 text-sm">
                {locale === "el"
                  ? "Μη έγκυρη υπογραφή. Δοκιμάστε νέα επαλήθευση."
                  : "Invalid signature. Try re-verifying."}
              </div>
            )}

            {voteStatus === "error" && voteError && (
              <div className="bg-red-900/50 border border-red-700 rounded-xl p-4 text-red-300 text-sm">
                {voteError}
              </div>
            )}

            <p className="text-gray-600 text-xs mt-3">
              {locale === "el"
                ? "Η ψηφοφορία δεν είναι νομικά δεσμευτική."
                : "This vote is not legally binding."}
            </p>
          </div>
        )}

        {/* ── ERGEBNISSE ── */}
        {results && results.total_votes > 0 && (
          <div className="bg-gray-900 rounded-2xl p-6 mb-6 border border-gray-800">
            <h2 className="font-bold text-lg mb-4">
              📊 {locale === "el" ? "Αποτελέσματα Πολιτών" : "Citizen Results"}
            </h2>
            <p className="text-gray-400 text-sm mb-4">
              {results.total_votes.toLocaleString()}{" "}
              {locale === "el" ? "ψήφοι" : "votes"}
            </p>

            {/* Ergebnis-Bars */}
            {[
              { label: locale === "el" ? "Υπέρ" : "Yes",     pct: results.yes_percent,     color: "bg-green-500" },
              { label: locale === "el" ? "Κατά" : "No",      pct: results.no_percent,      color: "bg-red-500" },
              { label: locale === "el" ? "Αποχή" : "Abstain",pct: results.abstain_percent, color: "bg-gray-500" },
            ].map(bar => (
              <div key={bar.label} className="mb-3">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-300">{bar.label}</span>
                  <span className="font-semibold">{bar.pct}%</span>
                </div>
                <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${bar.color} rounded-full transition-all duration-700`}
                    style={{ width: `${bar.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Divergence Score */}
        {results?.divergence && (
          <div className="mb-6">
            <DivergenceCard divergence={results.divergence} locale={locale} />
          </div>
        )}

        {/* Disclaimer */}
        <p className="text-gray-600 text-xs text-center leading-relaxed">
          {results?.disclaimer_el ||
            "Η ψηφοφορία αυτή δεν είναι νομικά δεσμευτική και εκφράζει μόνο τη γνώμη των εγγεγραμμένων χρηστών."}
        </p>
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
