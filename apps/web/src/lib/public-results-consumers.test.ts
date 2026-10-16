import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { describe, expect, it } from "vitest";

function testDocument() {
  const nodes = new Map<string, { textContent: string; innerHTML: string; style: Record<string, string>; setAttribute: () => void }>();
  return { getElementById(id: string) {
    if (!nodes.has(id)) nodes.set(id, { textContent: "", innerHTML: "", style: {}, setAttribute() {} });
    return nodes.get(id)!;
  }, nodes };
}
const docs = new URL("../../../../docs/", import.meta.url);
const read = (name: string) => readFileSync(new URL(name, docs), "utf8");
const withheld = {
  bill_id: "TEST", total_votes: 41, yes_pct: null, no_pct: null, abstain_pct: null,
  yes_count: null as number | null, no_count: null as number | null, abstain_count: null as number | null,
  yes_percent: null as number | null, no_percent: null as number | null, abstain_percent: null as number | null,
  suppressed: true, suppression_k: 10,
};

describe("public results consumers", () => {
  it.each([null, 0, 41])("community turnout preserves %s", (total) => {
    const html = read("community.html");
    const start = html.indexOf("      var s=d.stats||{};");
    const end = html.indexOf("    }).catch", start);
    const document = testDocument();
    runInNewContext(html.slice(start, end), { document, d: { stats: { total_votes: total } } });
    expect(document.getElementById("ss-votes").textContent).toBe(total == null ? "—" : total);
  });

  it.each([["el", 41], ["en", 41], ["el", null], ["en", null]] as const)("landing labels preserve null choices in %s (total %s)", (lang, total) => {
    const html = read("index.html");
    const start = html.indexOf("  function setLiveText(");
    const end = html.indexOf("  function phases()", start);
    const ids = ["resultTotal", "resultParticipation", "resultMajority", "resultYesLabel", "resultNoLabel", "demoYesLabel", "demoNoLabel", "resultYes", "resultNo", "yesBar", "noBar"];
    const document = testDocument();
    ids.forEach(id => document.getElementById(id));
    runInNewContext(`${html.slice(start, end)};renderLiveResult(data);fillResultData();`, {
      document, window: { _liveResult: withheld }, currentLang: lang, data: { ...withheld, total_votes: total },
    });
    const text = [...document.nodes.values()].map(n => n.textContent).join(" ");
    expect(text).toContain(lang === "en" ? "Majority: —" : "Πλειοψηφία: —");
    expect(text).not.toMatch(/0%|Majority: YES|Πλειοψηφία: ΥΠΕΡ/);
    expect(document.getElementById("resultTotal")?.textContent).toContain(total == null ? "—" : "41");
  });

  it.each(["results", "vote"])("%s embed preserves nulls and reads API fields", (embed) => {
    for (const lang of ["el", "en"]) {
      const html = read(`embed/${embed}.html`);
      const document = testDocument();
      const window = { location: { search: `?bill_id=TEST&lang=${lang}` }, addEventListener() {} };
      const script = html.match(/<script>([\s\S]*?)<\/script>/)![1];
      const context = { window, document, URLSearchParams,
        fetch: () => new Promise(() => {}), setInterval: () => 0, data: withheld };
      runInNewContext(`${script};render({title_el:"Test",status:"PARLIAMENT_VOTED",party_votes_parliament:{A:"YES"}},data);`, context);
      let text = document.getElementById("widget").innerHTML;
      expect(text).toContain("—");
      expect(text).toContain("41");
      expect(text).not.toMatch(/0%|No votes yet|Δεν υπάρχουν ψήφοι ακόμα|Divergence Score|Δείκτης Απόκλισης/);
      context.data = { ...withheld, total_votes: 40, yes_count: 10, no_count: 10, abstain_count: 10,
        yes_percent: 25, no_percent: 25, abstain_percent: 25 };
      runInNewContext('render({title_el:"Test",status:"PARLIAMENT_VOTED"},data);', context);
      text = document.getElementById("widget").innerHTML;
      expect(text).toContain("25%");
      expect(text).toContain("40");
    }
  });
});
