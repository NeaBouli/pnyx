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

type Phase = "intro" | "quiz" | "results";

export default function VAAPage() {
  const t = useTranslations("vaa");
  const tCommon = useTranslations("common");
  const locale = useLocale();

  const [phase, setPhase] = useState<Phase>("intro");
  const [statements, setStatements] = useState<Statement[]>([]);
  const [parties, setParties] = useState<Party[]>([]);
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [results, setResults] = useState<PartyMatchResult[]>([]);
  const [, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Thesen laden
  useEffect(() => {
    ekklesia.getStatements()
      .then(r => setStatements(r.data))
      .catch(() => setError("API nicht erreichbar"));
    ekklesia.getParties()
      .then(r => setParties(r.data))
      .catch(() => {});
  }, []);

  const stmt = statements[current];
  const isLast = current === statements.length - 1;
  const label = locale === "el" ? "text_el" : "text_en";
  const explLabel = locale === "el" ? "explanation_el" : "explanation_en";

  function answer(value: number) {
    if (!stmt) return;
    setAnswers(prev => ({ ...prev, [stmt.id]: value }));
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
      const r = await ekklesia.match(answers);
      setResults(r.data.results);
      setPhase("results");
    } catch {
      setError("Fehler beim Berechnen der Ergebnisse.");
    } finally {
      setLoading(false);
    }
  }

  // ── INTRO ────────────────────────────────────────────────────────────────
  if (phase === "intro") {
    return (
      <main className="min-h-screen bg-gray-950 text-white">
        <header className="border-b border-gray-800 px-6 py-4">
          <Link href="." className="text-blue-400 font-bold text-xl">
            ← εκκλησία
          </Link>
        </header>
        <div className="max-w-2xl mx-auto px-6 py-20 text-center">
          <div className="text-5xl mb-6">🗳️</div>
          <h1 className="text-4xl font-bold mb-4">{t("title")}</h1>
          <p className="text-gray-400 mb-8 text-lg">{t("subtitle")}</p>
          <div className="bg-gray-900 rounded-2xl p-6 mb-8 text-left space-y-3 border border-gray-800">
            <p className="text-gray-300">
              📋 <strong>{statements.length || 15}</strong> {locale === "el" ? "θέσεις" : "positions"}
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
          {error && (
            <div className="bg-red-900/50 border border-red-700 rounded-xl p-4 mb-6 text-red-300">
              {error} — API läuft? <code>cd apps/api && uvicorn main:app</code>
            </div>
          )}
          <button
            onClick={() => setPhase("quiz")}
            disabled={statements.length === 0}
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
        <header className="border-b border-gray-800 px-6 py-4 flex justify-between items-center">
          <Link href="." className="text-blue-400 font-bold">εκκλησία</Link>
          <span className="text-gray-400 text-sm">{stmt.category}</span>
        </header>

        <div className="max-w-2xl mx-auto px-6 py-10">
          {/* Progress */}
          <div className="mb-10">
            <ProgressBar current={current + 1} total={statements.length} />
          </div>

          {/* These */}
          <div className="bg-gray-900 rounded-2xl p-8 mb-6 border border-gray-800">
            <p className="text-xl font-semibold leading-relaxed mb-4">
              {stmt[label] || stmt.text_el}
            </p>
            {stmt[explLabel] && (
              <p className="text-gray-400 text-sm leading-relaxed border-t border-gray-800 pt-4">
                ℹ️ {stmt[explLabel]}
              </p>
            )}
          </div>

          {/* Antwort-Buttons */}
          <div className="grid grid-cols-2 gap-3 mb-8">
            <VoteButton label={t("agree")}    value={1}  selected={selected === 1}  onClick={answer} />
            <VoteButton label={t("disagree")} value={-1} selected={selected === -1} onClick={answer} />
            <VoteButton label={t("neutral")}  value={0}  selected={selected === 0}  onClick={answer} />
            <VoteButton label={t("dont_know")} value={0} selected={false} onClick={() => {
              answer(0);
            }} />
          </div>

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
        <header className="border-b border-gray-800 px-6 py-4 flex justify-between items-center">
          <Link href="." className="text-blue-400 font-bold">εκκλησία</Link>
          <button
            onClick={() => { setPhase("intro"); setCurrent(0); setAnswers({}); }}
            className="text-gray-400 hover:text-white text-sm transition-colors"
          >
            ↩ {locale === "el" ? "Επανάληψη" : "Restart"}
          </button>
        </header>

        <div className="max-w-2xl mx-auto px-6 py-10">
          <h1 className="text-3xl font-bold mb-2">{t("your_results")}</h1>
          <p className="text-gray-400 mb-8">
            {locale === "el"
              ? `Απαντήσατε σε ${Object.keys(answers).length} θέσεις`
              : `You answered ${Object.keys(answers).length} positions`}
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
            {results.map((r, i) => (
              <div key={r.party_id}
                className="flex items-center gap-4 bg-gray-900 rounded-xl p-4 border border-gray-800">
                <span className="text-2xl font-bold text-gray-600 w-8">
                  {i + 1}
                </span>
                <div
                  className="w-3 h-12 rounded-full flex-shrink-0"
                  style={{ backgroundColor: r.color_hex || "#3b82f6" }}
                />
                <div className="flex-1">
                  <p className="font-semibold">{r.name_el}</p>
                  <p className="text-gray-400 text-sm">{r.abbreviation}</p>
                </div>
                <span className="text-2xl font-bold"
                  style={{ color: r.color_hex || "#3b82f6" }}>
                  {r.match_percent}%
                </span>
              </div>
            ))}
          </div>

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
              🏛️ {locale === "el" ? "Δείτε τα Νομοσχέδια" : "See Bills"} →
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return null;
}
