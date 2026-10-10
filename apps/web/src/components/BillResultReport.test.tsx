import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import BillResultReport from "./BillResultReport";

const props = {
  billId: "SYN-1",
  titleEl: "Synthetic",
  totalVotes: 10,
  yesCount: 6,
  noCount: 3,
  abstainCount: 1,
  unknownCount: 0,
  yesPct: 60,
  noPct: 30,
  abstainPct: 10,
  divergence: { score: 0.5, label_el: "x", citizen_majority: "ΥΠΕΡ", parliament_result: "ΑΠΟΡΡΙΦΘΗΚΕ" },
  representativity: {
    total_votes: 10, eligible_voters: 1000, population: null, participation_pct: 1, population_pct: null,
    level: "low", color: "#ef4444", label_el: "x", is_representative: false, score: 10, headline_el: "x",
  },
  partyVotes: { A: "ΝΑΙ", B: "ΟΧΙ" },
  parliamentVoteDate: "2026-01-15",
};

const headings = {
  el: ["Απόφαση Βουλής", "Βούληση Πολιτών — εκκλησία του έθνους", "Απόκλιση Βουλής — Πολιτών", "Αντιπροσωπευτικότητα"],
  en: ["Parliamentary Decision", "Citizen Will", "Parliament vs Citizens", "Representativeness"],
};

describe("BillResultReport subsection headings", () => {
  it.each(["el", "en"] as const)("renders the three fixed headings (plus unchanged citizen heading) with gray-600 in %s", (locale) => {
    const html = renderToStaticMarkup(<BillResultReport {...props} locale={locale} />);
    const h3s = [...html.matchAll(/<h3 class="([^"]*)">([^<]*)<\/h3>/g)];
    expect(h3s.map((m) => m[2])).toEqual(headings[locale]);
    for (const [, cls] of h3s) {
      expect(cls.split(" ")).toEqual(["text-sm", "font-bold", "text-gray-600", "uppercase", "tracking-wider", "mb-3"]);
      expect(cls).not.toContain("text-gray-400");
    }
    expect(html).toContain('<div class="rounded-2xl border border-gray-200 bg-white overflow-hidden mb-6">');
    expect(html.match(/<h2[^>]*>/g)).toHaveLength(1);
  });
});
