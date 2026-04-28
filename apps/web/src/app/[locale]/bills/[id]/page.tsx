"use client";

import { useState, useEffect } from "react";
import { useLocale } from "next-intl";
import Link from "next/link";
import { ekklesia, Bill, BillResults } from "@/lib/api";
import { loadKeypair, loadNullifier, signVote } from "@/lib/crypto";
import StatusBadge from "@/components/StatusBadge";
import RelevanceButtons from "@/components/RelevanceButtons";
import BillResultReport from "@/components/BillResultReport";
// CompassCard removed — compass is mobile-app only
import QRCodeVoteStub from "@/components/QRCodeVoteStub";

const VOTE_OPTIONS = [
  { value: "YES",     label_el: "Υπέρ",               label_en: "Yes",            color: "bg-green-600 hover:bg-green-700 border-green-500 text-white" },
  { value: "NO",      label_el: "Κατά",               label_en: "No",             color: "bg-red-600 hover:bg-red-700 border-red-500 text-white" },
  { value: "ABSTAIN", label_el: "Αποχή",              label_en: "Abstain",        color: "bg-gray-500 hover:bg-gray-600 border-gray-400 text-white" },
  { value: "UNKNOWN", label_el: "Δεν γνωρίζω αρκετά", label_en: "Don't know enough", color: "bg-yellow-500 hover:bg-yellow-600 border-yellow-400 text-white" },
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
  const [aiSummary, setAiSummary] = useState<string>("");
  const [aiLoading, setAiLoading] = useState(false);

  const titleKey = locale === "el" ? "title_el" : "title_en";
  const shortKey = locale === "el" ? "summary_short_el" : "summary_short_en";
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.ekklesia.gr";

  useEffect(() => {
    Promise.all([
      ekklesia.getBill(billId),
      ekklesia.getResults(billId),
    ]).then(([billRes, resultsRes]) => {
      setBill(billRes.data);
      setResults(resultsRes.data);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [billId]);

  // Fetch AI summary when "Ανάλυση" tab is clicked
  useEffect(() => {
    if (expanded !== "long" || aiSummary || aiLoading) return;
    setAiLoading(true);
    fetch(`${API_URL}/api/v1/bills/${encodeURIComponent(billId)}/summary?lang=${locale}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.summary) setAiSummary(d.summary); })
      .catch(() => {})
      .finally(() => setAiLoading(false));
  }, [expanded, billId, locale, aiSummary, aiLoading, API_URL]);

  async function handleVoteClick(choice: string) {
    const keypair = loadKeypair();
    const nullifier = loadNullifier();

    if (!keypair || !nullifier) {
      setVoteStatus("needs_key");
      setSelectedVote(choice);
      return;
    }

    setVoteLoading(true);
    setVoteError(null);
    setSelectedVote(choice);

    try {
      const signatureHex = signVote(keypair.privateKeyHex, {
        bill_id: billId,
        vote: choice,
        nullifier_hash: nullifier,
      });

      const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.ekklesia.gr";
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
        // compass recording is mobile-app only
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
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-400 animate-pulse">
          {locale === "el" ? "Φόρτωση..." : "Loading..."}
        </div>
      </main>
    );
  }

  if (!bill) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-4">
            🏛️
          </div>
          <p className="text-gray-600 font-medium">
            {locale === "el" ? "Νομοσχέδιο δεν βρέθηκε" : "Bill not found"}
          </p>
          <Link href="../bills" className="mt-4 inline-block text-blue-600 hover:text-blue-700 font-semibold text-sm">
            ← {locale === "el" ? "Πίσω" : "Back"}
          </Link>
        </div>
      </main>
    );
  }

  const canVote = VOTABLE.includes(bill.status);

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-2xl mx-auto px-6 py-10">
        {/* Back link */}
        <Link href="../bills" className="text-blue-600 text-sm hover:text-blue-700 mb-6 inline-flex items-center gap-1 font-medium">
          ← {locale === "el" ? "Πίσω στα Νομοσχέδια" : "Back to Bills"}
        </Link>

        {/* Status + ID */}
        <div className="flex justify-between items-center mb-4 mt-4">
          <StatusBadge status={bill.status} locale={locale} />
          <span className="text-xs text-gray-400 font-mono">{bill.id}</span>
        </div>

        {/* Official Parliament Link + Jina Reader fallback (WAF bypass) */}
        {(bill as any).parliament_url && (
          <div className="flex items-center gap-2 flex-wrap mb-4">
            <a
              href={(bill as any).parliament_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 transition-colors font-medium"
            >
              🏛️ {locale === "el" ? "Επίσημο κείμενο στη Βουλή →" : "Official Parliament text →"}
            </a>
            <span className="text-xs text-gray-400">
              ({locale === "el" ? "αν δεν ανοίγει:" : "if blocked:"}
              <a
                href={`https://r.jina.ai/${(bill as any).parliament_url}`}
                target="_blank"
                rel="noopener noreferrer"
                className="underline ml-1 hover:text-gray-600"
                title={locale === "el" ? "Μέσω Jina Reader — τρίτος πάροχος" : "Via Jina Reader — third-party provider"}
              >
                {locale === "el" ? "εναλλακτικός σύνδεσμος ↗" : "alternative link ↗"}
              </a>)
            </span>
          </div>
        )}

        {/* Relevance */}
        <div className="flex items-center gap-3 mb-4">
          <span className="text-sm text-gray-500">
            {locale === "el" ? "Σημαντικότητα:" : "Importance:"}
          </span>
          <RelevanceButtons billId={billId} locale={locale} />
        </div>

        {/* Title */}
        <h1 className="text-2xl font-black text-gray-900 leading-snug mb-6">
          {bill[titleKey as keyof Bill] as string || bill.title_el}
        </h1>

        {/* Categories */}
        {bill.categories && (
          <div className="flex gap-2 mb-6 flex-wrap">
            {bill.categories.map(cat => (
              <span key={cat} className="px-3 py-1 bg-blue-50 text-blue-700 rounded-lg text-xs font-medium">
                {cat}
              </span>
            ))}
          </div>
        )}

        {/* Summary */}
        <div className="bg-white rounded-2xl p-6 mb-6 border border-gray-200">
          <div className="flex gap-3 mb-4">
            {["short", "long"].map(level => (
              <button
                key={level}
                onClick={() => setExpanded(level as "short" | "long")}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  expanded === level
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-500 hover:text-gray-900"
                }`}
              >
                {level === "short"
                  ? (locale === "el" ? "Σύνοψη" : "Summary")
                  : (locale === "el" ? "Ανάλυση" : "Analysis")}
              </button>
            ))}
            {(bill as any).forum_topic_id && (
              <a
                href={`https://pnyx.ekklesia.gr/t/${(bill as any).forum_topic_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 rounded-lg text-sm font-semibold transition-colors bg-gray-100 text-gray-500 hover:text-gray-900 hover:bg-gray-200 inline-flex items-center gap-1"
              >
                {locale === "el" ? "Συζήτηση" : "Discussion"}
              </a>
            )}
          </div>
          {expanded === "short" ? (
            <p className="text-gray-700 leading-relaxed">
              {bill[shortKey as keyof Bill] as string || bill.pill_el || "—"}
            </p>
          ) : (
            <div className="text-gray-700 leading-relaxed">
              {aiLoading ? (
                <div className="flex items-center gap-2 text-gray-400 text-sm animate-pulse">
                  <span>AI</span>
                  {locale === "el" ? "Φόρτωση ανάλυσης..." : "Loading analysis..."}
                </div>
              ) : aiSummary ? (
                <div className="whitespace-pre-line">{aiSummary}</div>
              ) : (bill.summary_long_el || bill.summary_long_en) ? (
                <p>{locale === "el" ? bill.summary_long_el : (bill.summary_long_en || bill.summary_long_el)}</p>
              ) : (
                <p className="text-gray-400">{locale === "el" ? "Δεν υπάρχει ανάλυση ακόμα." : "No analysis available yet."}</p>
              )}
            </div>
          )}
        </div>

        {/* ── VOTING ── */}
        {canVote && (
          <div className="bg-white rounded-2xl p-6 mb-6 border border-gray-200">
            <h2 className="font-bold text-lg text-gray-900 mb-4">
              {locale === "el" ? "Η ψήφος σας" : "Your vote"}
            </h2>

            <div className="grid grid-cols-2 gap-3 mb-4">
              {VOTE_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => handleVoteClick(opt.value)}
                  disabled={voteLoading || voteStatus === "voted"}
                  className={`py-4 px-4 rounded-xl font-semibold border-2 transition-all ${opt.color} ${
                    selectedVote === opt.value
                      ? "ring-2 ring-blue-600 scale-105"
                      : "opacity-90"
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
              <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-yellow-800 text-sm">
                <p className="font-semibold mb-2">
                  {locale === "el"
                    ? "Απαιτείται επαλήθευση ταυτότητας"
                    : "Identity verification required"}
                </p>
                <p className="text-yellow-700 text-xs">
                  {locale === "el"
                    ? "Κατεβάστε την εφαρμογή εκκλησία για να επαληθεύσετε την ταυτότητά σας και να ψηφίσετε."
                    : "Download the ekklesia app to verify your identity and vote."}
                </p>
              </div>
            )}

            {voteStatus === "voted" && (
              <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-green-800 text-sm">
                ✓ {locale === "el"
                  ? `Ψήφος "${selectedVote}" καταγράφηκε με Ed25519 υπογραφή.`
                  : `Vote "${selectedVote}" recorded with Ed25519 signature.`}
              </div>
            )}

            {voteStatus === "already" && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-yellow-800 text-sm">
                {locale === "el"
                  ? "Έχετε ήδη ψηφίσει για αυτό το νομοσχέδιο."
                  : "You have already voted on this bill."}
              </div>
            )}

            {voteStatus === "invalid_sig" && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-800 text-sm">
                {locale === "el"
                  ? "Μη έγκυρη υπογραφή. Δοκιμάστε νέα επαλήθευση."
                  : "Invalid signature. Try re-verifying."}
              </div>
            )}

            {voteStatus === "error" && voteError && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-800 text-sm">
                {voteError}
              </div>
            )}

            <p className="text-gray-400 text-xs mt-3">
              {locale === "el"
                ? "Η ψηφοφορία δεν είναι νομικά δεσμευτική."
                : "This vote is not legally binding."}
            </p>
          </div>
        )}

        {/* ── QR CODE STUB ── */}
        <div className="mb-6">
          <QRCodeVoteStub billId={billId} purpose="vote" />
        </div>


        {/* ── FULL RESULT REPORT ── */}
        {results && results.total_votes > 0 && (
          <BillResultReport
            billId={billId}
            titleEl={bill?.title_el || ""}
            totalVotes={results.total_votes}
            yesCount={results.yes_count}
            noCount={results.no_count}
            abstainCount={results.abstain_count}
            yesPct={results.yes_percent}
            noPct={results.no_percent}
            abstainPct={results.abstain_percent}
            divergence={results.divergence}
            representativity={(results as unknown as Record<string, unknown>).representativity as never ?? null}
            partyVotes={bill?.party_votes_parliament || null}
            parliamentVoteDate={bill?.parliament_vote_date || null}
            locale={locale}
          />
        )}
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
