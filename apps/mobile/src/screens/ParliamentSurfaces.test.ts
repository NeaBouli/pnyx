import { readFileSync } from "node:fs";
import vm from "node:vm";
import { URL } from "node:url";
import ts from "typescript";
import { describe, expect, it, vi } from "vitest";
import { colors } from "../theme";
import * as resolver from "../lib/source-resolver";
import * as provenance from "../lib/parliament-source";
import * as results from "../lib/results-display";
import { parliamentFreshness } from "../lib/source-freshness";
import ParliamentAttribution from "../components/ParliamentAttribution";

vi.mock("react-native", () => ({
  View: "View", Text: "Text", TouchableOpacity: "TouchableOpacity",
  StyleSheet: { create: (value: unknown) => value }, Linking: { openURL: vi.fn() },
}));

type Node = { type: unknown; props: Record<string, any> };
function nodes(value: any): Node[] {
  if (Array.isArray(value)) return value.flatMap(nodes);
  if (!value?.props) return [];
  return [value, ...nodes(value.props.children)];
}
function text(value: any): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(text).join("");
  return value?.props ? text(value.props.children) : "";
}

const original = "  Άρθρο 1 — *επίσημο* _κείμενο_ https://hellenicparliament.gr/πηγή\n\n".repeat(50)
  + "### Πλήρη έγγραφα\n- [PDF](https://www.hellenicparliament.gr/a.pdf)\n";
const imported = {
  bill_id: "GR-IMPORTED", id: "GR-IMPORTED", title_el: "Αυθεντικός *τίτλος* _πλήρης_ ".repeat(12),
  status: "ANNOUNCED", source: "PARLIAMENT", created_at: "2026-01-01T23:30:00",
  parliament_url: "https://www.hellenicparliament.gr/bill/123", official_source_url: null,
  pill_el: "Δική μας σύνοψη", summary_short_el: "Δική μας σύνοψη", analysis_el: "Δική μας ανάλυση", summary_long_el: original,
  total_votes: 0, results_hidden: true,
};

/** Render the production screen and its attribution, with native APIs and effects
 * disabled. State values represent the completed API load, not a second renderer.
 */
function screen(name: "Trending" | "Result" | "Vote", bill: typeof imported): Node {
  let index = 0;
  const state = name === "Trending" ? [[bill], false]
    : name === "Result" ? [bill, false, false]
      : [bill.title_el, false, null, bill.summary_short_el, bill.analysis_el, false,
        resolver.cleanOfficialText(bill.summary_long_el, provenance.hasParliamentProvenance(bill)), bill,
        [], bill.status, true, "NATIONAL", bill.source, ""];
  const react: Record<string, any> = {
    useState: (initial: unknown) => [index < state.length ? state[index++] : (index++, initial), vi.fn()],
    useEffect: vi.fn(), useCallback: (fn: unknown) => fn,
    createElement(type: any, props: any, ...children: any[]) {
      const all = { ...props, children };
      return typeof type === "function" ? type(all) : { type, props: all };
    },
  };
  const native = Object.fromEntries(["View", "Text", "FlatList", "TouchableOpacity", "ActivityIndicator", "ScrollView", "RefreshControl"].map(name => [name, name]));
  const modules: Record<string, any> = {
    react: { __esModule: true, default: react, ...react },
    "react-native": { ...native, StyleSheet: { create: (value: unknown) => value } },
    "@react-navigation/native": { useNavigation: () => ({}), useFocusEffect: vi.fn() },
    "../theme": { colors }, "../lib/source-resolver": resolver,
    "../lib/parliament-source": provenance, "../lib/results-display": results,
    "../lib/source-freshness": { parliamentFreshness },
    "../components/ParliamentAttribution": { __esModule: true, default: ParliamentAttribution },
    "../lib/zkPublicVoting": { canShowPublicZkVoting: () => false, canSubmitPublicZkVote: () => false },
  };
  const compiled = ts.transpileModule(readFileSync(new URL(`./${name}Screen.tsx`, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx: ts.JsxEmit.React },
  }).outputText;
  const exports: any = {};
  vm.runInNewContext(compiled, { exports, require: (name: string) => modules[name] ?? {}, process: { env: {} } });
  let tree = exports.default({ route: { params: { billId: bill.id } }, navigation: {} });
  if (name === "Trending") tree = tree.props.renderItem({ item: bill, index: 0 });
  return tree;
}

describe.each(["Trending", "Result", "Vote"] as const)("%s Parliament republication", name => {
  it("renders full official titles, attribution, source dates and editorial labels", () => {
    const tree = screen(name, imported);
    expect(text(tree)).toContain(imported.title_el);
    expect(text(tree)).toContain("Αναδημοσίευση από τη διαδικτυακή πύλη της Βουλής των Ελλήνων");
    expect(text(tree)).toContain("Ημερομηνία: 02/01/2026");
    expect(text(tree)).toContain("Σύνοψη — ekklesia");
    expect(text(tree)).toContain("Πρωτότυπο");
    if (name !== "Trending") {
      expect(text(tree)).toContain("Ανάλυση — ekklesia");
      expect(nodes(tree).some(node => node.type === "Text" && text(node) === original)).toBe(true);
    }
  });
  it("does not attribute legacy local proposals to Parliament", () => {
    const tree = screen(name, { ...imported, parliament_url: null } as unknown as typeof imported);
    expect(text(tree)).not.toContain("Αναδημοσίευση");
    expect(text(tree)).not.toContain("Πρωτότυπο");
    expect(text(tree)).not.toContain("— ekklesia");
  });
});
