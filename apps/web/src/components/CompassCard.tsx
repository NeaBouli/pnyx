"use client";

import { useLocale } from "next-intl";
import { useCompass } from "@/lib/compass";
import { MODEL_LABELS } from "@/lib/compass/dimension-map";

export default function CompassCard() {
  const locale = useLocale();
  const compass = useCompass();
  const isEl = locale === "el";

  if (compass.loading) return null;

  // Disabled state — compass is mobile-only
  if (!compass.isEnabled) {
    return (
      <div className="bg-blue-50 rounded-xl border border-blue-200 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl">🧭</span>
          <p className="text-sm text-gray-600">
            {isEl ? "Πολιτική Πυξίδα" : "Political Compass"}
          </p>
        </div>
        <a
          href="https://ekklesia.gr/#download"
          className="text-sm text-blue-600 hover:text-blue-700 font-medium transition-colors"
        >
          {isEl ? "Διαθέσιμη στην εφαρμογή →" : "Available in the app →"}
        </a>
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
    <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center justify-between">
      <div className="flex items-center gap-3 min-w-0">
        <span className="text-xl flex-shrink-0">🧭</span>
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{modelLabel}</p>
          <p className="text-xs text-gray-500">{summary}</p>
        </div>
      </div>
      <span className="text-sm text-blue-600 font-medium flex-shrink-0 ml-3">
        {isEl ? "Ενεργό" : "Active"}
      </span>
    </div>
  );
}
