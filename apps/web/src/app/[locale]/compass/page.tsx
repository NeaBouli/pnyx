"use client";

import { useState } from "react";
import { useLocale } from "next-intl";
import Link from "next/link";
import { useCompass } from "@/lib/compass";
import { MODEL_LABELS, THEMATIC_LABELS } from "@/lib/compass/dimension-map";
import type { CompassModel, ThematicArea } from "@/lib/compass/types";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from "recharts";

const MODEL_ICONS: Record<CompassModel, string> = {
  "party-match": "🏛️",
  "left-right": "↔️",
  "compass-2d": "🧭",
  "thematic-radar": "📊",
};

export default function CompassPage() {
  const locale = useLocale();
  const compass = useCompass();
  const [confirmReset, setConfirmReset] = useState(false);

  const isEl = locale === "el";

  // ── Model Selector Grid ──────────────────────────────────────────────────
  function ModelSelector({ compact }: { compact?: boolean }) {
    const models = Object.keys(MODEL_LABELS) as CompassModel[];
    return (
      <div className={`grid ${compact ? "grid-cols-2 sm:grid-cols-4 gap-2" : "grid-cols-1 sm:grid-cols-2 gap-4"}`}>
        {models.map((m) => {
          const label = MODEL_LABELS[m];
          const isActive = compass.selectedModel === m;
          return (
            <button
              key={m}
              onClick={() => compass.setModel(isActive ? null : m)}
              className={`rounded-xl p-4 border-2 text-left transition-all ${
                isActive
                  ? "bg-blue-950 border-blue-500 ring-1 ring-blue-400"
                  : "bg-gray-900 border-gray-800 hover:border-gray-600"
              }`}
            >
              <div className="text-2xl mb-2">{MODEL_ICONS[m]}</div>
              <p className="font-semibold text-sm">{isEl ? label.el : label.en}</p>
              {!compact && (
                <p className="text-xs text-gray-400 mt-1">{isEl ? label.desc_el : label.desc_en}</p>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  // ── Privacy Banner ───────────────────────────────────────────────────────
  function PrivacyBanner() {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-start gap-3">
        <span className="text-lg flex-shrink-0">🔒</span>
        <p className="text-xs text-gray-400 leading-relaxed">
          {isEl
            ? "Όλα τα δεδομένα της Πυξίδας αποθηκεύονται τοπικά στη συσκευή σας, κρυπτογραφημένα με το ιδιωτικό κλειδί σας. Κανένα δεδομένο δεν αποστέλλεται σε εξωτερικούς διακομιστές."
            : "All Compass data is stored locally on your device, encrypted with your private key. No data is sent to external servers."}
        </p>
      </div>
    );
  }

  // ── Visualization: Party Match ───────────────────────────────────────────
  function PartyMatchViz() {
    if (!compass.result || compass.result.model !== "party-match") return null;
    const chartData = compass.result.data.map((r) => ({
      name: r.abbreviation,
      value: r.matchPercent,
      color: r.colorHex,
    }));
    return (
      <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
        <h3 className="font-bold mb-4">{isEl ? "Κομματική Συμφωνία" : "Party Match"}</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 30 }}>
            <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fill: "#9ca3af" }} />
            <YAxis type="category" dataKey="name" tick={{ fill: "#e5e7eb" }} width={60} />
            <Tooltip
              formatter={(v: number) => [`${v}%`, isEl ? "Αντιστοίχιση" : "Match"]}
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
    );
  }

  // ── Visualization: Left-Right Gauge ──────────────────────────────────────
  function LeftRightViz() {
    if (!compass.result || compass.result.model !== "left-right") return null;
    const { position } = compass.result.data;
    const pct = ((position + 1) / 2) * 100; // -1→0%, +1→100%
    return (
      <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
        <h3 className="font-bold mb-6">{isEl ? "Αριστερά — Δεξιά" : "Left — Right"}</h3>
        <div className="relative h-12 bg-gradient-to-r from-red-900 via-gray-700 to-blue-900 rounded-full overflow-hidden">
          {/* Marker */}
          <div
            className="absolute top-0 h-full w-1 bg-white shadow-lg shadow-white/50 transition-all duration-500"
            style={{ left: `${pct}%` }}
          />
          {/* Dot */}
          <div
            className="absolute top-1/2 -translate-y-1/2 w-5 h-5 bg-white rounded-full border-2 border-blue-400 shadow-lg transition-all duration-500"
            style={{ left: `calc(${pct}% - 10px)` }}
          />
        </div>
        <div className="flex justify-between mt-3 text-xs text-gray-400">
          <span>{isEl ? "Αριστερά" : "Left"}</span>
          <span>{isEl ? "Κέντρο" : "Centre"}</span>
          <span>{isEl ? "Δεξιά" : "Right"}</span>
        </div>
        <p className="text-center mt-4 text-sm text-gray-300">
          {isEl ? "Θέση" : "Position"}: <span className="font-bold text-white">{position.toFixed(2)}</span>
        </p>
      </div>
    );
  }

  // ── Visualization: 2D Compass ────────────────────────────────────────────
  function Compass2DViz() {
    if (!compass.result || compass.result.model !== "compass-2d") return null;
    const { economic, social } = compass.result.data;
    // Map from [-1,+1] to [0, 200] SVG coords
    const cx = 100 + economic * 80;
    const cy = 100 - social * 80; // invert Y (liberal top)
    return (
      <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
        <h3 className="font-bold mb-4">{isEl ? "Πολιτική Πυξίδα 2D" : "2D Political Compass"}</h3>
        <div className="flex justify-center">
          <svg viewBox="0 0 200 200" className="w-full max-w-sm" xmlns="http://www.w3.org/2000/svg">
            {/* Background */}
            <rect x="10" y="10" width="180" height="180" rx="8" fill="#1f2937" />
            {/* Quadrant shading */}
            <rect x="10" y="10" width="90" height="90" fill="#7f1d1d" opacity="0.15" />
            <rect x="100" y="10" width="90" height="90" fill="#1e3a5f" opacity="0.15" />
            <rect x="10" y="100" width="90" height="90" fill="#1e3a5f" opacity="0.15" />
            <rect x="100" y="100" width="90" height="90" fill="#14532d" opacity="0.15" />
            {/* Crosshairs */}
            <line x1="100" y1="10" x2="100" y2="190" stroke="#4b5563" strokeWidth="1" />
            <line x1="10" y1="100" x2="190" y2="100" stroke="#4b5563" strokeWidth="1" />
            {/* Grid lines */}
            <line x1="55" y1="10" x2="55" y2="190" stroke="#374151" strokeWidth="0.5" strokeDasharray="4,4" />
            <line x1="145" y1="10" x2="145" y2="190" stroke="#374151" strokeWidth="0.5" strokeDasharray="4,4" />
            <line x1="10" y1="55" x2="190" y2="55" stroke="#374151" strokeWidth="0.5" strokeDasharray="4,4" />
            <line x1="10" y1="145" x2="190" y2="145" stroke="#374151" strokeWidth="0.5" strokeDasharray="4,4" />
            {/* User position */}
            <circle cx={cx} cy={cy} r="8" fill="#3b82f6" stroke="#93c5fd" strokeWidth="2" opacity="0.9" />
            <circle cx={cx} cy={cy} r="3" fill="#ffffff" />
            {/* Axis labels */}
            <text x="100" y="8" textAnchor="middle" fill="#9ca3af" fontSize="7">
              {isEl ? "Συντηρητικό" : "Conservative"}
            </text>
            <text x="100" y="198" textAnchor="middle" fill="#9ca3af" fontSize="7">
              {isEl ? "Φιλελεύθερο" : "Liberal"}
            </text>
            <text x="6" y="103" textAnchor="start" fill="#9ca3af" fontSize="6" transform="rotate(-90, 6, 103)">
              {isEl ? "Κράτος" : "State"}
            </text>
            <text x="196" y="103" textAnchor="start" fill="#9ca3af" fontSize="6" transform="rotate(90, 196, 103)">
              {isEl ? "Αγορά" : "Market"}
            </text>
          </svg>
        </div>
        <div className="flex justify-center gap-6 mt-4 text-xs text-gray-400">
          <span>{isEl ? "Οικονομία" : "Economic"}: <span className="text-white font-bold">{economic.toFixed(2)}</span></span>
          <span>{isEl ? "Κοινωνία" : "Social"}: <span className="text-white font-bold">{social.toFixed(2)}</span></span>
        </div>
      </div>
    );
  }

  // ── Visualization: Thematic Radar ────────────────────────────────────────
  function ThematicRadarViz() {
    if (!compass.result || compass.result.model !== "thematic-radar") return null;
    const { areas } = compass.result.data;
    const chartData = (Object.keys(THEMATIC_LABELS) as ThematicArea[]).map((key) => ({
      area: isEl ? THEMATIC_LABELS[key].el : THEMATIC_LABELS[key].en,
      value: Math.round(((areas[key]?.position ?? 0) + 1) * 50), // map [-1,+1] to [0, 100]
      dataPoints: areas[key]?.dataPoints ?? 0,
    }));
    return (
      <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800">
        <h3 className="font-bold mb-4">{isEl ? "Θεματικό Ραντάρ" : "Thematic Radar"}</h3>
        <ResponsiveContainer width="100%" height={350}>
          <RadarChart data={chartData} cx="50%" cy="50%" outerRadius="70%">
            <PolarGrid stroke="#374151" />
            <PolarAngleAxis dataKey="area" tick={{ fill: "#9ca3af", fontSize: 11 }} />
            <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: "#4b5563", fontSize: 9 }} />
            <Radar
              name={isEl ? "Θέση" : "Position"}
              dataKey="value"
              stroke="#3b82f6"
              fill="#3b82f6"
              fillOpacity={0.3}
              strokeWidth={2}
            />
            <Tooltip
              contentStyle={{ background: "#111827", border: "1px solid #374151" }}
              formatter={(v: number) => [`${v}`, isEl ? "Θέση" : "Position"]}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // ── Loading ──────────────────────────────────────────────────────────────
  if (compass.loading) {
    return (
      <main className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <div className="text-gray-400 animate-pulse">
          {isEl ? "Φόρτωση..." : "Loading..."}
        </div>
      </main>
    );
  }

  // ── STATE 1: Compass disabled ────────────────────────────────────────────
  if (!compass.isEnabled) {
    return (
      <main className="min-h-screen bg-gray-950 text-white">
        <div className="max-w-3xl mx-auto px-6 py-12">
          <div className="text-center mb-10">
            <div className="text-5xl mb-4">🧭</div>
            <h1 className="text-3xl font-bold mb-3">
              {isEl ? "Πολιτική Πυξίδα" : "Political Compass"}
            </h1>
            <p className="text-gray-400 text-lg">
              {isEl
                ? "Ενεργοποιήστε την Πυξίδα σας για να παρακολουθείτε πώς εξελίσσεται η πολιτική σας θέση."
                : "Activate your Compass to track how your political position evolves."}
            </p>
          </div>

          <div className="mb-8">
            <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4">
              {isEl ? "Επιλέξτε Μοντέλο" : "Choose Model"}
            </h2>
            <ModelSelector />
          </div>

          <PrivacyBanner />
        </div>
      </main>
    );
  }

  // ── STATE 2: Enabled but no data ─────────────────────────────────────────
  if (compass.dataPoints === 0) {
    return (
      <main className="min-h-screen bg-gray-950 text-white">
        <div className="max-w-3xl mx-auto px-6 py-12">
          <div className="text-center mb-10">
            <div className="text-5xl mb-4">🧭</div>
            <h1 className="text-3xl font-bold mb-3">
              {isEl ? "Πολιτική Πυξίδα" : "Political Compass"}
            </h1>
            <p className="text-gray-400">
              {isEl
                ? `Μοντέλο: ${MODEL_LABELS[compass.selectedModel!].el}`
                : `Model: ${MODEL_LABELS[compass.selectedModel!].en}`}
            </p>
          </div>

          <div className="bg-gray-900 rounded-2xl p-8 border border-gray-800 text-center mb-8">
            <p className="text-gray-400 mb-6">
              {isEl
                ? "Δεν υπάρχουν ακόμα δεδομένα. Ολοκληρώστε το VAA ή ψηφίστε σε νομοσχέδια για να ξεκινήσετε."
                : "No data yet. Complete the VAA or vote on bills to get started."}
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link
                href={`/${locale}/vaa`}
                className="px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-xl font-semibold transition-colors"
              >
                {isEl ? "Πολιτική Πυξίδα (VAA) →" : "Take the VAA →"}
              </Link>
              <Link
                href={`/${locale}/bills`}
                className="px-6 py-3 bg-gray-800 hover:bg-gray-700 rounded-xl font-semibold transition-colors"
              >
                {isEl ? "Νομοσχέδια →" : "Vote on Bills →"}
              </Link>
            </div>
          </div>

          <div className="mb-8">
            <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4">
              {isEl ? "Αλλαγή Μοντέλου" : "Switch Model"}
            </h2>
            <ModelSelector compact />
          </div>

          <PrivacyBanner />
        </div>
      </main>
    );
  }

  // ── STATE 3: Enabled with data ───────────────────────────────────────────
  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-3xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">
              {isEl ? "Πολιτική Πυξίδα" : "Political Compass"}
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              {isEl
                ? `Μοντέλο: ${MODEL_LABELS[compass.selectedModel!].el}`
                : `Model: ${MODEL_LABELS[compass.selectedModel!].en}`}
            </p>
          </div>
          <div className="text-5xl">🧭</div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-3 mb-8">
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 text-center">
            <p className="text-2xl font-bold text-blue-400">{compass.dataPoints}</p>
            <p className="text-xs text-gray-500">{isEl ? "Σημεία Δεδομένων" : "Data Points"}</p>
          </div>
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 text-center">
            <p className="text-2xl font-bold text-blue-400">{compass.billVoteCount}</p>
            <p className="text-xs text-gray-500">{isEl ? "Ψήφοι Νομοσχεδίων" : "Bill Votes"}</p>
          </div>
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 text-center">
            <p className="text-2xl font-bold text-blue-400">{compass.vaaCompleted ? "✓" : "—"}</p>
            <p className="text-xs text-gray-500">VAA</p>
          </div>
        </div>

        {/* Active Visualization */}
        <div className="mb-8">
          {compass.selectedModel === "party-match" && <PartyMatchViz />}
          {compass.selectedModel === "left-right" && <LeftRightViz />}
          {compass.selectedModel === "compass-2d" && <Compass2DViz />}
          {compass.selectedModel === "thematic-radar" && <ThematicRadarViz />}
        </div>

        {/* Model Switcher */}
        <div className="mb-8">
          <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-4">
            {isEl ? "Αλλαγή Μοντέλου" : "Switch Model"}
          </h2>
          <ModelSelector compact />
        </div>

        {/* Privacy Banner */}
        <div className="mb-6">
          <PrivacyBanner />
        </div>

        {/* Reset */}
        <div className="text-center">
          {!confirmReset ? (
            <button
              onClick={() => setConfirmReset(true)}
              className="text-sm text-gray-600 hover:text-red-400 transition-colors"
            >
              {isEl ? "Επαναφορά Πυξίδας" : "Reset Compass"}
            </button>
          ) : (
            <div className="bg-red-950 border border-red-800 rounded-xl p-4 inline-flex items-center gap-4">
              <p className="text-red-300 text-sm">
                {isEl ? "Σίγουρα; Θα διαγραφούν όλα τα δεδομένα." : "Are you sure? All data will be deleted."}
              </p>
              <button
                onClick={() => { compass.clearProfile(); setConfirmReset(false); }}
                className="px-4 py-2 bg-red-700 hover:bg-red-600 rounded-lg text-sm font-semibold transition-colors"
              >
                {isEl ? "Ναι, διαγραφή" : "Yes, delete"}
              </button>
              <button
                onClick={() => setConfirmReset(false)}
                className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm font-semibold transition-colors"
              >
                {isEl ? "Ακύρωση" : "Cancel"}
              </button>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
