"use client";

import { useState, useEffect } from "react";
import { useTranslations, useLocale } from "next-intl";
import Link from "next/link";
import ProgressBar from "@/components/ProgressBar";
import VoteButton from "@/components/VoteButton";
import { ekklesia, Statement, Party, PartyMatchResult } from "@/lib/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell
} from "recharts";
import { useCompass } from "@/lib/compass";

type Phase = "intro" | "quiz" | "results";
type AnswerValue = number | "skip";

export default function VAAPage() {
  const t = useTranslations("vaa");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const compass = useCompass();

  const [phase, setPhase] = useState<Phase>("intro");
  const [consentGiven, setConsentGiven] = useState(false);
  const [statements, setStatements] = useState<Statement[]>([]);
  const [parties, setParties] = useState<Party[]>([]);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<number, AnswerValue>>({});
  const [results, setResults] = useState<PartyMatchResult[]>([]);
  const [, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedParty, setExpandedParty] = useState<number | null>(null);

  // Thesen laden
  useEffect(() => {
    ekklesia.getStatements()
      .then(r => setStatements(r.data))
      .catch(() => setError("Σφάλμα σύνδεσης API"));
    ekklesia.getParties()
      .then(r => setParties(r.data))
      .catch(() => {});
  }, []);

  const stmt = statements[current];
  const isLast = current === statements.length - 1;
  const label = locale === "el" ? "text_el" : "text_en";
  const explLabel = locale === "el" ? "explanation_el" : "explanation_en";

  // Anzahl tatsächlich beantworteter Thesen (ohne skip)
  const answeredCount = Object.values(answers).filter(v => v !== "skip").length;

  function answer(value: number) {
    if (!stmt) return;
    setAnswers(prev => ({ ...prev, [stmt.id]: value }));
  }

  function skip() {
    if (!stmt) return;
    setAnswers(prev => ({ ...prev, [stmt.id]: "skip" }));
    advance();
  }

  function advance() {
    if (!isLast) {
      setCurrent(c => c + 1);
    } else {
      showResults();
    }
  }

  async function next() {
    if (!isLast) {
      setCurrent(c => c + 1);
    } else {
      await showResults();
    }
  }

  function back() {
    if (current > 0) setCurrent(c => c - 1);
  }

  async function showResults() {
    setLoading(true);
    try {
      // Filter out skipped answers before sending to API
      const filtered = Object.fromEntries(
        Object.entries(answers).filter(([, v]) => v !== "skip")
      ) as Record<number, number>;
      const r = await ekklesia.match(filtered);
      setResults(r.data.results);
      compass.seedFromVAA(filtered);
      setPhase("results");
    } catch {
      setError("Σφάλμα κατά τον υπολογισμό αποτελεσμάτων.");
    } finally {
      setLoading(false);
    }
  }

  async function shareResults() {
    if (!results.length) return;
    const top = results[0];
    const shareData = {
      title: locale === "el" ? "Πολιτική μου Πυξίδα — εκκλησία" : "My Political Compass — ekklesia",
      text: locale === "el"
        ? `${top.name_el} (${top.match_percent}%) — Βρες και εσύ τον πολιτικό σου χάρτη!`
        : `${top.name_el} (${top.match_percent}%) — Find your political compass!`,
      url: "https://ekklesia.gr/vaa",
    };
    if (navigator.share) {
      try { await navigator.share(shareData); } catch { /* cancelled */ }
    } else {
      await navigator.clipboard.writeText(`${shareData.text} ${shareData.url}`);
    }
  }

  // ── INTRO ────────────────────────────────────────────────────────────────
  if (phase === "intro") {
    return (
      <main className="min-h-screen bg-gray-950 text-white">
        <div className="max-w-2xl mx-auto px-6 py-20 text-center">
          <div className="text-5xl mb-6">🗳️</div>
          <h1 className="text-4xl font-bold mb-4">{t("title")}</h1>
          <p className="text-gray-400 mb-8 text-lg">{t("subtitle")}</p>
          <div className="bg-gray-900 rounded-2xl p-6 mb-8 text-left space-y-3 border border-gray-800">
            <p className="text-gray-300">
              📋 <strong>{statements.length || 38}</strong> {locale === "el" ? "θέσεις" : "positions"}
            </p>
            <p className="text-gray-300">
              🏛️ <strong>{parties.length || 8}</strong> {locale === "el" ? "κόμματα" : "parties"}
            </p>
            <p className="text-gray-300">
              ⏱️ ~5 {locale === "el" ? "λεπτά" : "minutes"}
            </p>
            <p className="text-gray-300">
              🔐 {locale === "el" ? "Ανώνυμο — Δεν αποθηκεύονται δεδομένα" : "Anonymous — No data stored"}
            </p>
          </div>

          {/* Art. 9 GDPR Consent */}
          <div className="bg-gray-900 rounded-xl p-4 mb-6 border border-yellow-800 text-left">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={consentGiven}
                onChange={e => setConsentGiven(e.target.checked)}
                className="mt-1 w-4 h-4 accent-blue-600 flex-shrink-0"
              />
              <span className="text-sm text-gray-300 leading-relaxed">
                {locale === "el"
                  ? "Κατανοώ ότι οι απαντήσεις μου αποθηκεύονται ψευδώνυμα, συνδεδεμένες με το δημόσιο κλειδί μου, αποκλειστικά για τη δημιουργία του πολιτικού μου προφίλ. Μπορώ να τις διαγράψω ανά πάσα στιγμή μέσω της ανάκλησης ταυτότητας."
                  : "I understand that my answers are stored pseudonymously, linked to my public key, solely to generate my political compass result. I can delete them at any time via identity revocation."}
              </span>
            </label>
          </div>

          {error && (
            <div className="bg-red-900/50 border border-red-700 rounded-xl p-4 mb-6 text-red-300">
              {error}
            </div>
          )}
          <button
            onClick={() => setPhase("quiz")}
            disabled={statements.length === 0 || !consentGiven}
            className="px-10 py-4 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-xl font-bold text-xl transition-colors"
          >
            {statements.length === 0 ? tCommon("loading") : t("next") + " →"}
          </button>
        </div>
      </main>
    );
  }

  // ── QUIZ ─────────────────────────────────────────────────────────────────
  if (phase === "quiz" && stmt) {
    const selected = answers[stmt.id];
    return (
      <main className="min-h-screen bg-gray-950 text-white">
        <div className="max-w-2xl mx-auto px-6 py-10">
          <div className="text-right text-gray-500 text-sm mb-4">
            {current + 1} / {statements.length}
          </div>
          {/* Progress */}
          <div className="mb-10">
            <ProgressBar current={current + 1} total={statements.length} />
          </div>

          {/* These */}
          <div className="bg-gray-900 rounded-2xl p-8 mb-6 border border-gray-800">
            {/* Kategorie-Badge */}
            {stmt.category && (
              <span className="text-xs font-bold text-blue-400 uppercase tracking-wider mb-3 block">
                {stmt.category}
              </span>
            )}
            <p className="text-xl font-semibold leading-relaxed mb-4">
              {stmt[label] || stmt.text_el}
            </p>
            {stmt[explLabel] && (
              <p className="text-gray-400 text-sm leading-relaxed border-t border-gray-800 pt-4">
                {stmt[explLabel]}
              </p>
            )}
          </div>

          {/* Antwort-Buttons */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <VoteButton label={t("agree")}    value={1}  selected={selected === 1}  onClick={answer} />
            <VoteButton label={t("disagree")} value={-1} selected={selected === -1} onClick={answer} />
            <VoteButton label={t("neutral")}  value={0}  selected={selected === 0}  onClick={answer} />
          </div>

          {/* Δεν ξέρω — Skip */}
          <button
            onClick={skip}
            className="w-full py-3 mb-8 text-gray-500 hover:text-gray-300 text-sm font-medium transition-colors"
          >
            {locale === "el" ? "Δεν ξέρω / Παράλειψη →" : "Don't know / Skip →"}
          </button>

          {/* Navigation */}
          <div className="flex gap-4">
            {current > 0 && (
              <button
                onClick={back}
                className="flex-1 py-3 bg-gray-800 hover:bg-gray-700 rounded-xl font-semibold transition-colors"
              >
                ← {t("back")}
              </button>
            )}
            <button
              onClick={next}
              disabled={selected === undefined}
              className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-xl font-semibold transition-colors"
            >
              {isLast ? t("see_results") : t("next") + " →"}
            </button>
          </div>
        </div>
      </main>
    );
  }

  // ── RESULTS ───────────────────────────────────────────────────────────────
  if (phase === "results") {
    const chartData = results.map(r => ({
      name: r.abbreviation || r.name_el,
      value: r.match_percent,
      color: r.color_hex || "#3b82f6",
    }));

    return (
      <main className="min-h-screen bg-gray-950 text-white">
        <div className="max-w-2xl mx-auto px-6 py-10">
          <div className="flex justify-end gap-3 mb-4">
            <button
              onClick={shareResults}
              className="text-blue-400 hover:text-blue-300 text-sm font-medium transition-colors"
            >
              {locale === "el" ? "Κοινοποίηση" : "Share"}
            </button>
            <button
              onClick={() => { setPhase("intro"); setCurrent(0); setAnswers({}); setExpandedParty(null); }}
              className="text-gray-400 hover:text-white text-sm transition-colors"
            >
              ↩ {locale === "el" ? "Επανάληψη" : "Restart"}
            </button>
          </div>
          <h1 className="text-3xl font-bold mb-2">{t("your_results")}</h1>
          <p className="text-gray-400 mb-8">
            {locale === "el"
              ? `Απαντήσατε σε ${answeredCount} από ${statements.length} θέσεις`
              : `You answered ${answeredCount} of ${statements.length} positions`}
          </p>

          {/* Balkendiagramm */}
          <div className="bg-gray-900 rounded-2xl p-6 mb-6 border border-gray-800">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData} layout="vertical"
                margin={{ left: 20, right: 30 }}>
                <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fill: "#9ca3af" }} />
                <YAxis type="category" dataKey="name" tick={{ fill: "#e5e7eb" }} width={60} />
                <Tooltip
                  formatter={(v: number) => [`${v}%`, t("match")]}
                  contentStyle={{ background: "#111827", border: "1px solid #374151" }}
                />
                <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Rangliste */}
          <div className="space-y-3 mb-8">
            {results.map((r, i) => {
              const isTop = i === 0;
              const isExpanded = expandedParty === r.party_id;

              return (
                <div key={r.party_id}>
                  <button
                    onClick={() => setExpandedParty(isExpanded ? null : r.party_id)}
                    className={`w-full flex items-center gap-4 rounded-xl p-4 border text-left transition-all ${
                      isTop
                        ? "bg-yellow-950/40 border-yellow-600/60 ring-1 ring-yellow-500/30"
                        : "bg-gray-900 border-gray-800 hover:border-gray-600"
                    }`}
                  >
                    <span className={`text-2xl font-bold w-8 ${isTop ? "text-yellow-400" : "text-gray-600"}`}>
                      {isTop ? "🥇" : i + 1}
                    </span>
                    <div
                      className="w-3 h-12 rounded-full flex-shrink-0"
                      style={{ backgroundColor: r.color_hex || "#3b82f6" }}
                    />
                    <div className="flex-1 min-w-0">
                      <p className={`font-semibold ${isTop ? "text-lg" : ""}`}>{r.name_el}</p>
                      <p className="text-gray-400 text-sm">{r.abbreviation}</p>
                      {isTop && (
                        <p className="text-yellow-500 text-xs font-bold mt-1">
                          {locale === "el" ? "Καλύτερη Αντιστοίχιση" : "Best Match"}
                        </p>
                      )}
                    </div>
                    <span className={`text-2xl font-bold ${isTop ? "text-3xl" : ""}`}
                      style={{ color: r.color_hex || "#3b82f6" }}>
                      {r.match_percent}%
                    </span>
                    <span className="text-gray-600 text-sm ml-1">
                      {isExpanded ? "▲" : "▼"}
                    </span>
                  </button>

                  {/* Party Detail — Übereinstimmungen pro These */}
                  {isExpanded && (
                    <div className="mt-1 bg-gray-900/60 border border-gray-800 rounded-xl p-4 space-y-2">
                      <p className="text-xs text-gray-500 font-bold uppercase tracking-wider mb-3">
                        {locale === "el" ? "Σύγκριση ανά θέση" : "Comparison per position"}
                      </p>
                      {statements.map(s => {
                        const userAns = answers[s.id];
                        if (userAns === "skip" || userAns === undefined) return null;
                        const posLabel = (v: number | undefined) =>
                          v === 1 ? (locale === "el" ? "Υπέρ" : "Agree")
                          : v === -1 ? (locale === "el" ? "Κατά" : "Disagree")
                          : (locale === "el" ? "Ουδέτερο" : "Neutral");
                        return (
                          <div key={s.id} className="flex items-center gap-2 text-sm">
                            <span className="text-gray-500 w-5 text-right flex-shrink-0">{s.display_order}.</span>
                            <span className="flex-1 text-gray-300 truncate">{s[label] || s.text_el}</span>
                            <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                              userAns === 1 ? "bg-green-900/50 text-green-400"
                              : userAns === -1 ? "bg-red-900/50 text-red-400"
                              : "bg-gray-800 text-gray-400"
                            }`}>
                              {posLabel(userAns as number)}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Share Button */}
          <button
            onClick={shareResults}
            className="w-full py-3 mb-6 bg-gray-800 hover:bg-gray-700 rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
          >
            <span>{locale === "el" ? "Κοινοποίηση Αποτελεσμάτων" : "Share Results"}</span>
          </button>

          {/* Bills CTA */}
          <div className="bg-blue-950 border border-blue-800 rounded-2xl p-6 text-center">
            <p className="text-blue-300 mb-4">
              {locale === "el"
                ? "Ψηφίστε τώρα για πραγματικά νομοσχέδια της Βουλής"
                : "Now vote on real parliamentary bills"}
            </p>
            <Link
              href="../bills"
              className="inline-block px-8 py-3 bg-blue-600 hover:bg-blue-500 rounded-xl font-semibold transition-colors"
            >
              {locale === "el" ? "Δείτε τα Νομοσχέδια" : "See Bills"} →
            </Link>
          </div>

          {/* Compass CTA */}
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mt-6 text-center">
            <div className="text-3xl mb-3">🧭</div>
            <p className="text-gray-300 mb-4">
              {locale === "el"
                ? "Οι απαντήσεις σας τροφοδοτούν τώρα την εξελισσόμενη Πολιτική σας Πυξίδα."
                : "Your answers now feed your evolving Political Compass."}
            </p>
            <Link
              href={`/${locale}/compass`}
              className="inline-block px-8 py-3 bg-gray-800 hover:bg-gray-700 rounded-xl font-semibold transition-colors"
            >
              {locale === "el" ? "Δείτε την Πυξίδα" : "View Compass"} →
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return null;
}
