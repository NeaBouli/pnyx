"use client";

import { useEffect, useState } from "react";
import { DivergenceResult } from "@/lib/api";

interface Props {
  divergence: DivergenceResult;
  locale?: string;
}

export default function DivergenceCard({ divergence, locale = "el" }: Props) {
  const pct = Math.round(divergence.score * 100);
  const [animated, setAnimated] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(pct), 100);
    return () => clearTimeout(timer);
  }, [pct]);

  const high   = pct > 40;
  const medium = pct > 20;

  const color = high
    ? { bg: "bg-red-950",    border: "border-red-700",    text: "text-red-400",    bar: "bg-red-500" }
    : medium
    ? { bg: "bg-yellow-950", border: "border-yellow-700", text: "text-yellow-400", bar: "bg-yellow-500" }
    : { bg: "bg-green-950",  border: "border-green-700",  text: "text-green-400",  bar: "bg-green-500" };

  const icon = high ? "⚠️" : medium ? "⚡" : "✓";

  const label = locale === "el"
    ? divergence.label_el
    : (high ? "High Divergence" : medium ? "Moderate Divergence" : "Convergence");

  return (
    <div className={`rounded-2xl p-6 border ${color.bg} ${color.border}`}>
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
            {locale === "el" ? "Δείκτης Απόκλισης" : "Divergence Score"}
          </span>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-lg">{icon}</span>
            <span className={`font-bold ${color.text}`}>{label}</span>
          </div>
        </div>
        <div className={`text-5xl font-black ${color.text}`}>
          {animated}%
        </div>
      </div>

      {/* Animated Bar */}
      <div className="h-3 bg-gray-800 rounded-full overflow-hidden mb-5">
        <div
          className={`h-full ${color.bar} rounded-full transition-all duration-1000 ease-out`}
          style={{ width: `${animated}%` }}
        />
      </div>

      {/* Citizen vs Parliament */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-gray-900 rounded-xl p-3 text-center border border-gray-800">
          <div className="text-xs text-gray-500 mb-1">
            {locale === "el" ? "Πλειοψηφία Πολιτών" : "Citizen Majority"}
          </div>
          <div className="font-bold text-sm text-white">
            {divergence.citizen_majority}
          </div>
        </div>
        <div className="bg-gray-900 rounded-xl p-3 text-center border border-gray-800">
          <div className="text-xs text-gray-500 mb-1">
            {locale === "el" ? "Απόφαση Βουλής" : "Parliament Decision"}
          </div>
          <div className="font-bold text-sm text-white">
            {divergence.parliament_result || "—"}
          </div>
        </div>
      </div>

      {/* Headline */}
      {divergence.headline_el && (
        <p className={`text-sm ${color.text} font-semibold text-center`}>
          {divergence.headline_el}
        </p>
      )}
    </div>
  );
}
