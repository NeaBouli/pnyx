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

const VOTABLE = ["ACTIVE", "WINDOW_24H"];

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
  const [qrSessionId, setQrSessionId] = useState<string | null>(null);
  const [consensusScore, setConsensusScore] = useState<number>(0);
  const [consensusSubmitting, setConsensusSubmitting] = useState(false);
  const [consensusDone, setConsensusDone] = useState(false);

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

    // Path A: Local Ed25519 keys exist → sign and submit directly
    if (keypair && nullifier) {
      setVoteLoading(true);
      setVoteError(null);
      setSelectedVote(choice);
      try {
        const signatureHex = signVote(keypair.privateKeyHex, {
          bill_id: billId,
          vote: choice,
          nullifier_hash: nullifier,
        });
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
          try { const r = await ekklesia.getResults(billId); setResults(r.data); } catch {}
        } else if (res.status === 409) { setVoteStatus("already"); }
        else if (res.status === 401) { setVoteStatus("invalid_sig"); }
        else { const e = await res.json().catch(() => ({})); setVoteError(e.detail || `Error ${res.status}`); setVoteStatus("error"); }
      } catch (err) {
        setVoteError(err instanceof Error ? err.message : "Network error");
        setVoteStatus("error");
      } finally { setVoteLoading(false); }
      return;
    }

    // Path B: QR session authenticated → vote via session proxy
    if (qrSessionId) {
      setVoteLoading(true);
      setVoteError(null);
      setSelectedVote(choice);
      try {
        const res = await fetch(`${API_URL}/api/v1/polis/qr-vote`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: qrSessionId,
            bill_id: billId,
            vote: choice,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok && data.success) {
          setVoteStatus("voted");
          setQrSessionId(null); // consumed
          try { const r = await ekklesia.getResults(billId); setResults(r.data); } catch {}
        } else if (res.status === 409) { setVoteStatus("already"); }
        else { setVoteError(data.detail || `Error ${res.status}`); setVoteStatus("error"); }
      } catch (err) {
        setVoteError(err instanceof Error ? err.message : "Network error");
        setVoteStatus("error");
      } finally { setVoteLoading(false); }
      return;
    }

    // Path C: No keys, no QR session → prompt to scan QR below
    setVoteStatus("needs_key");
    setSelectedVote(choice);
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

        {/* Region Banner */}
        {(bill as any).governance_level === "REGIONAL" && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-4 text-sm">
            <span className="font-bold text-blue-700">📍 {locale === "el" ? "Περιφερειακή ψηφοφορία" : "Regional vote"}</span>
            <span className="text-blue-500 ml-2">{locale === "el" ? "— Αφορά μόνο τους κατοίκους της περιοχής" : "— Only for residents of this region"}</span>
          </div>
        )}
        {(bill as any).governance_level === "MUNICIPAL" && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-4 text-sm">
            <span className="font-bold text-blue-700">📍 {locale === "el" ? "Δημοτική ψηφοφορία" : "Municipal vote"}</span>
            <span className="text-blue-500 ml-2">{locale === "el" ? "— Αφορά μόνο τους κατοίκους του Δήμου" : "— Only for residents of this municipality"}</span>
          </div>
        )}
        {(bill as any).governance_level === "INSTITUTIONAL" && bill.pill_el && (
          <div className="bg-purple-50 border border-purple-200 rounded-xl px-4 py-3 mb-4 text-sm">
            <span className="font-bold text-purple-700">🏢 {bill.pill_el}</span>
          </div>
        )}

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
                    ? "Σκανάρετε τον κωδικό QR παρακάτω με την εφαρμογή ekklesia για να ψηφίσετε από τον browser."
                    : "Scan the QR code below with the ekklesia app to vote from the browser."}
                </p>
              </div>
            )}

            {qrSessionId && voteStatus === "idle" && (
              <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-green-800 text-sm">
                ✅ {locale === "el"
                  ? "Ταυτοποίηση επιτυχής — πατήστε ένα κουμπί για να ψηφίσετε."
                  : "Authenticated — click a button to vote."}
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

        {/* ── QR CODE — nur bei abstimmungsbereiten Bills ── */}
        {bill && VOTABLE.includes(bill.status) && (
          <div className="mb-6">
            <QRCodeVoteStub
              billId={billId}
              purpose="vote"
              onAuthenticated={(sid) => {
                setQrSessionId(sid);
                setVoteStatus("idle");
                setVoteError(null);
              }}
            />
          </div>
        )}


        {/* ── Konsensierung für OPEN_END Bills ── */}
        {bill?.status === "OPEN_END" && (
          <div className="bg-purple-50 border border-purple-200 rounded-2xl p-6 mb-6">
            <h3 className="text-lg font-bold text-purple-800 mb-2">
              ⚖️ {locale === "el" ? "Κλίμακα Συναίνεσης" : "Consensus Scale"}
            </h3>
            <p className="text-purple-600 text-sm mb-4">
              {locale === "el"
                ? (bill as any).source === "DIAVGEIA"
                  ? "Πόσο συμφωνείτε με αυτή την απόφαση;"
                  : "Πόσο συμφωνείτε με την απόφαση της Βουλής;"
                : "How much do you agree with this decision?"}
            </p>

            {consensusDone ? (
              <div className="text-center py-4">
                <div className="text-3xl mb-2">✅</div>
                <p className="text-purple-800 font-bold">
                  {locale === "el" ? "Η αξιολόγησή σας καταγράφηκε!" : "Your rating has been recorded!"}
                </p>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between text-xs text-gray-500 mb-2">
                  <span>{locale === "el" ? "Αντίσταση" : "Resistance"}</span>
                  <span>{locale === "el" ? "Ουδέτερο" : "Neutral"}</span>
                  <span>{locale === "el" ? "Συναίνεση" : "Consensus"}</span>
                </div>
                <div className="flex gap-1.5 justify-center flex-wrap">
                  {[-5,-4,-3,-2,-1,0,1,2,3,4,5].map(v => (
                    <button
                      key={v}
                      onClick={() => setConsensusScore(v)}
                      disabled={!qrSessionId}
                      className={`w-10 h-10 flex items-center justify-center rounded-lg text-xs font-bold border transition-all ${
                        consensusScore === v
                          ? v > 0 ? "bg-green-600 text-white border-green-700 scale-110" :
                            v < 0 ? "bg-red-600 text-white border-red-700 scale-110" :
                            "bg-gray-600 text-white border-gray-700 scale-110"
                          : !qrSessionId
                            ? "bg-gray-100 text-gray-300 border-gray-200 cursor-not-allowed"
                            : v > 0 ? "bg-green-50 text-green-700 border-green-200 hover:bg-green-100 cursor-pointer" :
                              v < 0 ? "bg-red-50 text-red-700 border-red-200 hover:bg-red-100 cursor-pointer" :
                              "bg-gray-50 text-gray-500 border-gray-200 hover:bg-gray-100 cursor-pointer"
                      }`}
                    >
                      {v > 0 ? "+" : ""}{v}
                    </button>
                  ))}
                </div>
                <div className="text-center mt-3 text-2xl font-black" style={{
                  color: consensusScore > 0 ? "#16a34a" : consensusScore < 0 ? "#dc2626" : "#6b7280"
                }}>
                  {consensusScore > 0 ? "+" : ""}{consensusScore}
                </div>

                {qrSessionId ? (
                  <button
                    onClick={async () => {
                      setConsensusSubmitting(true);
                      try {
                        const r = await fetch("https://api.ekklesia.gr/api/v1/polis/qr-consensus", {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({
                            session_id: qrSessionId,
                            bill_id: billId,
                            score: consensusScore,
                          }),
                        });
                        if (r.ok) {
                          setConsensusDone(true);
                        } else {
                          const d = await r.json().catch(() => ({}));
                          const msg = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail || "Σφάλμα");
                          alert(msg);
                        }
                      } catch {
                        alert("Σφάλμα σύνδεσης");
                      } finally {
                        setConsensusSubmitting(false);
                      }
                    }}
                    disabled={consensusSubmitting}
                    className="mt-4 w-full py-3 bg-purple-600 text-white font-bold rounded-xl hover:bg-purple-700 transition-colors disabled:opacity-50"
                  >
                    {consensusSubmitting
                      ? "..."
                      : locale === "el" ? "Υποβολή Αξιολόγησης" : "Submit Rating"}
                  </button>
                ) : (
                  <div className="mt-4">
                    <p className="text-xs text-purple-500 text-center mb-3">
                      {locale === "el"
                        ? "Σαρώστε τον κωδικό QR με την εφαρμογή εκκλησία για να ξεκλειδώσετε την αξιολόγηση"
                        : "Scan the QR code with the ekklesia app to unlock rating"}
                    </p>
                    <QRCodeVoteStub
                      billId={billId}
                      purpose="consensus"
                      onAuthenticated={(sid) => {
                        setQrSessionId(sid);
                      }}
                    />
                  </div>
                )}
              </>
            )}

            {(bill as any).consensus_count > 0 && !consensusDone && (
              <div className="mt-4 text-center border-t border-purple-200 pt-3">
                <span className="text-xl font-black text-purple-700">
                  {((bill as any).consensus_score || 0) > 0 ? "+" : ""}{((bill as any).consensus_score || 0).toFixed(1)}
                </span>
                <span className="text-sm text-purple-500 ml-2">
                  ({(bill as any).consensus_count} {locale === "el" ? "αξιολογήσεις" : "ratings"})
                </span>
              </div>
            )}
          </div>
        )}

        {/* Results hidden message for ACTIVE bills */}
        {results && results.total_votes === 0 && bill?.status === "ACTIVE" && (
          <div className="bg-blue-50 border border-blue-200 rounded-2xl p-6 mb-6 text-center">
            <div className="text-4xl mb-3">🗳️</div>
            <p className="text-blue-800 font-semibold mb-1">
              {locale === "el" ? "Η ψήφος σας καταγράφηκε" : "Your vote has been recorded"}
            </p>
            <p className="text-blue-600 text-sm">
              {locale === "el"
                ? `Τα αποτελέσματα θα είναι διαθέσιμα μετά την ολοκλήρωση της ψηφοφορίας στη Βουλή${bill.parliament_vote_date ? ` (${new Date(bill.parliament_vote_date).toLocaleDateString("el-GR")})` : ""}.`
                : `Results will be available after the parliamentary vote${bill.parliament_vote_date ? ` (${new Date(bill.parliament_vote_date).toLocaleDateString("en-GB")})` : ""}.`}
            </p>
          </div>
        )}

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
          © 2026 V-Labs Development — MIT License —{" "}
          <a href="https://github.com/NeaBouli/pnyx" className="hover:text-gray-600" target="_blank">
            Open Source
          </a>
        </p>
      </footer>
    </main>
  );
}
