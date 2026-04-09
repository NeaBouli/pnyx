"use client";

import Link from "next/link";
import { useLocale } from "next-intl";
import { useCompass } from "@/lib/compass";
import { MODEL_LABELS } from "@/lib/compass/dimension-map";

export default function CompassCard() {
  const locale = useLocale();
  const compass = useCompass();
  const isEl = locale === "el";

  if (compass.loading) return null;

  // Disabled state
  if (!compass.isEnabled) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl">🧭</span>
          <p className="text-sm text-gray-400">
            {isEl ? "Πολιτική Πυξίδα" : "Political Compass"}
          </p>
        </div>
        <Link
          href={`/${locale}/compass`}
          className="text-sm text-blue-400 hover:text-blue-300 font-medium transition-colors"
        >
          {isEl ? "Ενεργοποίηση Πυξίδας →" : "Activate Compass →"}
        </Link>
      </div>
    );
  }

  // Enabled state
  const modelLabel = isEl
    ? MODEL_LABELS[compass.selectedModel!].el
    : MODEL_LABELS[compass.selectedModel!].en;

  const summary = compass.dataPoints > 0
    ? `${compass.dataPoints} ${isEl ? "σημεία" : "points"}`
    : (isEl ? "Χωρίς δεδομένα ακόμα" : "No data yet");

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 flex items-center justify-between">
      <div className="flex items-center gap-3 min-w-0">
        <span className="text-xl flex-shrink-0">🧭</span>
        <div className="min-w-0">
          <p className="text-sm font-medium text-white truncate">{modelLabel}</p>
          <p className="text-xs text-gray-500">{summary}</p>
        </div>
      </div>
      <Link
        href={`/${locale}/compass`}
        className="text-sm text-blue-400 hover:text-blue-300 font-medium transition-colors flex-shrink-0 ml-3"
      >
        {isEl ? "Άνοιγμα Πυξίδας →" : "Open Compass →"}
      </Link>
    </div>
  );
}
