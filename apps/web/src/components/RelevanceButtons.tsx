"use client";

import { useState } from "react";
import { voteRelevance } from "@/lib/api";
import { loadNullifier } from "@/lib/crypto";

interface Props {
  billId: string;
  initialScore?: number;
  locale?: string;
  compact?: boolean;
}

export default function RelevanceButtons({
  billId,
  initialScore = 0,
  locale = "el",
  compact = false,
}: Props) {
  const [score, setScore] = useState(initialScore);
  const [voted, setVoted] = useState<1 | -1 | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleVote(signal: 1 | -1) {
    if (voted !== null || loading) return;

    const nullifier = loadNullifier();
    if (!nullifier) return;

    setLoading(true);
    try {
      await voteRelevance(billId, signal, nullifier);
      setScore((s) => s + signal);
      setVoted(signal);
    } catch {
      setVoted(signal); // already voted
    } finally {
      setLoading(false);
    }
  }

  const btnBase = compact
    ? "flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold transition-all border-2"
    : "flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-bold transition-all border-2";

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => handleVote(1)}
        disabled={loading || voted !== null}
        title={locale === "el" ? "Σημαντικό" : "Important"}
        className={`${btnBase} ${
          voted === 1
            ? "bg-blue-600 border-blue-600 text-white"
            : "bg-transparent border-gray-700 text-gray-400 hover:border-blue-500 hover:text-blue-400"
        } ${loading || voted !== null ? "opacity-60 cursor-not-allowed" : ""}`}
      >
        ▲{!compact && ` ${locale === "el" ? "Σημαντικό" : "Important"}`}
      </button>

      <span
        className={`font-black tabular-nums ${compact ? "text-sm" : "text-base"} ${
          score > 0 ? "text-blue-400" : score < 0 ? "text-gray-600" : "text-gray-500"
        }`}
      >
        {score > 0 ? "+" : ""}
        {score}
      </span>

      <button
        onClick={() => handleVote(-1)}
        disabled={loading || voted !== null}
        title={locale === "el" ? "Λιγότερο σημαντικό" : "Less important"}
        className={`${btnBase} ${
          voted === -1
            ? "bg-gray-700 border-gray-600 text-white"
            : "bg-transparent border-gray-700 text-gray-600 hover:border-gray-500 hover:text-gray-400"
        } ${loading || voted !== null ? "opacity-60 cursor-not-allowed" : ""}`}
      >
        ▼{!compact && ` ${locale === "el" ? "Λιγότερο" : "Less"}`}
      </button>

      {voted !== null && (
        <span className="text-xs text-gray-600">
          {locale === "el" ? "✓" : "✓"}
        </span>
      )}
    </div>
  );
}
