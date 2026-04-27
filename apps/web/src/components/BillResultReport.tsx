"use client";

import { useEffect, useState } from "react";

interface Props {
  billId: string;
  titleEl: string;
  totalVotes: number;
  yesCount: number;
  noCount: number;
  abstainCount: number;
  yesPct: number;
  noPct: number;
  abstainPct: number;
  divergence: { score: number; label_el: string; citizen_majority: string; parliament_result: string | null; headline_el?: string } | null;
  representativity: { total_votes: number; eligible_voters: number; population: number; participation_pct: number; population_pct: number; level: string; color: string; label_el: string; is_representative: boolean; score: number; headline_el: string } | null;
  partyVotes: Record<string, string> | null;
  parliamentVoteDate: string | null;
  locale: string;
}

export default function BillResultReport({
  totalVotes, yesCount, noCount, abstainCount, yesPct, noPct, abstainPct,
  divergence, representativity, partyVotes, parliamentVoteDate, locale,
}: Props) {
  const [repAnim, setRepAnim] = useState(0);
  const el = (a: string, b: string) => locale === "el" ? a : b;

  useEffect(() => {
    if (representativity?.score) setTimeout(() => setRepAnim(representativity.score), 200);
  }, [representativity?.score]);

  const divScore = divergence ? Math.round(divergence.score * 100) : null;
  const repColor = representativity?.color || "#94a3b8";

  const pvLabel = (v: string) => {
    if (["ΝΑΙ", "YES"].includes(v)) return { l: "ΝΑΙ", c: "#22c55e" };
    if (["ΟΧΙ", "NO"].includes(v)) return { l: "ΟΧΙ", c: "#ef4444" };
    return { l: v, c: "#f59e0b" };
  };

  const parlYes = partyVotes ? Object.values(partyVotes).filter(v => ["ΝΑΙ", "YES"].includes(v)).length : 0;
  const parlNo = partyVotes ? Object.values(partyVotes).filter(v => ["ΟΧΙ", "NO"].includes(v)).length : 0;
  const divergedFromCitizens = divergence &&
    ((divergence.citizen_majority === "ΥΠΕΡ" && divergence.parliament_result === "ΑΠΟΡΡΙΦΘΗΚΕ") ||
     (divergence.citizen_majority === "ΚΑΤΑ" && divergence.parliament_result === "ΕΓΚΡΙΘΗΚΕ"));

  return (
    <div className="rounded-2xl border border-gray-200 bg-white overflow-hidden mb-6">
      <div className="px-6 py-4 bg-gray-800 border-b border-gray-200">
        <h2 className="font-black text-lg">{el("Πλήρης Έκθεση Αποτελεσμάτων", "Full Results Report")}</h2>
      </div>
      <div className="p-6 space-y-6">

        {/* Parliament */}
        {partyVotes && (
          <div>
            <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">
              {el("Απόφαση Βουλής", "Parliamentary Decision")}
            </h3>
            <div className="bg-gray-800 rounded-xl p-4">
              {parliamentVoteDate && (
                <p className="text-sm text-gray-300 mb-3">
                  {el("Η Βουλή ψήφισε στις", "Parliament voted on")}{" "}
                  <strong className="text-white">
                    {new Date(parliamentVoteDate).toLocaleDateString(locale === "el" ? "el-GR" : "en-GB", { day: "numeric", month: "long", year: "numeric" })}
                  </strong>
                  {" — "}
                  <strong className="text-green-400">{parlYes} ΝΑΙ</strong> / <strong className="text-red-400">{parlNo} ΟΧΙ</strong>
                </p>
              )}
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(partyVotes).map(([abbr, vote]) => {
                  const { l, c } = pvLabel(vote);
                  return (
                    <div key={abbr} className="flex justify-between bg-white rounded-lg px-3 py-2">
                      <span className="font-bold text-sm text-gray-200">{abbr}</span>
                      <span className="font-black text-sm" style={{ color: c }}>{l}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Citizen Votes */}
        <div>
          <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">
            {el("Βούληση Πολιτών — εκκλησία του έθνους", "Citizen Will")}
          </h3>
          <div className="bg-gray-800 rounded-xl p-4">
            <p className="text-sm text-gray-300 mb-4">
              <strong className="text-white">{totalVotes.toLocaleString()}</strong>{" "}
              {el("πολίτες ψήφισαν", "citizens voted")}.{" "}
              <strong className={yesPct > noPct ? "text-green-400" : "text-red-400"}>
                {yesPct > noPct ? el("Υπέρ", "Yes") : el("Κατά", "No")} ({Math.max(yesPct, noPct)}%)
              </strong>
            </p>
            {[
              { label: el("Υπέρ", "Yes"), pct: yesPct, count: yesCount, color: "bg-green-500", tc: "text-green-400" },
              { label: el("Κατά", "No"), pct: noPct, count: noCount, color: "bg-red-500", tc: "text-red-400" },
              { label: el("Αποχή", "Abstain"), pct: abstainPct, count: abstainCount, color: "bg-gray-500", tc: "text-gray-400" },
            ].map(b => (
              <div key={b.label} className="mb-3">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-300">{b.label}</span>
                  <span className={`font-black ${b.tc}`}>{b.pct}% <span className="text-gray-500 font-normal">({b.count.toLocaleString()})</span></span>
                </div>
                <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
                  <div className={`h-full ${b.color} rounded-full transition-all duration-700`} style={{ width: `${b.pct}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Divergence */}
        {divergence && divScore !== null && (
          <div>
            <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">
              {el("Απόκλιση Βουλής — Πολιτών", "Parliament vs Citizens")}
            </h3>
            <div className={`rounded-xl p-4 border ${divScore > 40 ? "bg-red-950 border-red-800" : divScore > 20 ? "bg-yellow-950 border-yellow-800" : "bg-green-950 border-green-800"}`}>
              <p className={`text-sm font-bold mb-3 ${divergedFromCitizens ? "text-red-300" : "text-green-300"}`}>
                {divergedFromCitizens
                  ? el(`Η Βουλή ψήφισε ΕΝΑΝΤΙΟΝ της πλειοψηφίας (${divScore}% απόκλιση)`, `Parliament voted AGAINST majority (${divScore}%)`)
                  : el(`Σύγκλιση Βουλής — Πολιτών (${divScore}% απόκλιση)`, `Parliament — Citizens convergence (${divScore}%)`)}
              </p>
              <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all duration-1000 ${divScore > 40 ? "bg-red-500" : divScore > 20 ? "bg-yellow-500" : "bg-green-500"}`} style={{ width: `${divScore}%` }} />
              </div>
            </div>
          </div>
        )}

        {/* Representativity */}
        {representativity && (
          <div>
            <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">
              {el("Αντιπροσωπευτικότητα", "Representativeness")}
            </h3>
            <div className="bg-gray-800 rounded-xl p-4">
              <p className="text-sm text-gray-300 mb-3">
                {totalVotes.toLocaleString()} / {representativity.eligible_voters.toLocaleString()} {el("εκλογείς", "voters")} ={" "}
                <strong style={{ color: repColor }}>{representativity.participation_pct.toFixed(4)}%</strong>.{" "}
                <span className={representativity.is_representative ? "text-green-300" : "text-yellow-300"}>
                  {representativity.headline_el}
                </span>
              </p>
              <div className="mb-2">
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-gray-500">Score</span>
                  <span className="font-black" style={{ color: repColor }}>{repAnim.toFixed(1)}/100</span>
                </div>
                <div className="h-4 bg-gray-700 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${repAnim}%`, backgroundColor: repColor }} />
                </div>
                <div className="flex justify-between text-xs text-gray-600 mt-1">
                  <span style={{ color: "#ef4444" }}>0%</span>
                  <span style={{ color: "#f59e0b" }}>50%</span>
                  <span style={{ color: "#2563eb" }}>100%</span>
                </div>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: repColor }} />
                <span className="font-bold text-sm" style={{ color: repColor }}>{representativity.label_el}</span>
              </div>
            </div>
          </div>
        )}

        <p className="text-xs text-gray-600 text-center pt-2 border-t border-gray-200">
          {el("Η ψηφοφορία δεν είναι νομικά δεσμευτική.", "This vote is not legally binding.")}
        </p>
      </div>
    </div>
  );
}
