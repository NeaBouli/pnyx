import { readFileSync } from "node:fs";
import vm from "node:vm";
import { URL } from "node:url";
import ts from "typescript";
import { describe, expect, it, vi } from "vitest";
import { colors } from "../theme";
import * as sourceResolver from "../lib/source-resolver";
import * as voteSuccess from "../lib/vote-success";
import * as zkPilotError from "../lib/zkPilotError";
import * as zkPublicVoting from "../lib/zkPublicVoting";

type El = { type: unknown; props: Record<string, any> };
type Status = { has_voted: boolean; is_correction: boolean; vote: string | null };

/**
 * Minimal React stub so the REAL VoteScreen runs in a vm context without
 * react-native. Unlike a throwing setter (the screen's try/catch would
 * swallow it), every post-unmount setState is counted so it stays observable.
 */
function createHarness() {
  const stateSlots: unknown[] = [];
  const effectSlots: ({ deps: unknown[] | undefined; cleanup?: unknown } | undefined)[] = [];
  let stateIdx = 0;
  let effIdx = 0;
  let component: (() => El) | null = null;
  let tree: El | null = null;
  let alive = false;
  let renders = 0;
  let lateSets = 0;
  let pending: { i: number; fn: () => unknown; deps: unknown[] | undefined }[] | null = null;

  const changed = (prev?: unknown[], next?: unknown[]) =>
    !prev || !next || prev.length !== next.length || next.some((d, i) => !Object.is(d, prev[i]));

  function render() {
    if (!component) return;
    stateIdx = effIdx = 0;
    renders += 1;
    const scheduled: NonNullable<typeof pending> = [];
    pending = scheduled;
    tree = component();
    pending = null;
    for (const p of scheduled) {
      const slot: { deps: unknown[] | undefined; cleanup?: unknown } = { deps: p.deps };
      effectSlots[p.i] = slot;
      slot.cleanup = p.fn();
    }
  }

  const api = {
    useState(init: unknown) {
      const i = stateIdx++;
      if (!(i in stateSlots)) stateSlots[i] = typeof init === "function" ? (init as () => unknown)() : init;
      const set = (v: unknown) => {
        if (!alive) { lateSets += 1; return; }
        stateSlots[i] = typeof v === "function" ? (v as (p: unknown) => unknown)(stateSlots[i]) : v;
        render();
      };
      return [stateSlots[i], set];
    },
    useEffect(fn: () => unknown, deps?: unknown[]) {
      const i = effIdx++;
      const prev = effectSlots[i];
      if (prev && !changed(prev.deps, deps)) return;
      if (prev && typeof prev.cleanup === "function") (prev.cleanup as () => void)();
      if (pending) pending.push({ i, fn, deps });
    },
    createElement(type: unknown, props?: Record<string, unknown> | null, ...children: unknown[]) {
      return { type, props: { ...(props ?? {}), children } };
    },
    Fragment: "Fragment",
  };

  function mount(comp: () => El) {
    component = comp;
    alive = true;
    render();
    return {
      tree: () => tree as El,
      unmount() {
        for (const slot of effectSlots) {
          if (slot && typeof slot.cleanup === "function") (slot.cleanup as () => void)();
        }
        alive = false;
      },
    };
  }

  return { api, mount, renderCount: () => renders, lateSets: () => lateSets };
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>(r => { resolve = r; });
  return { promise, resolve };
}

/** Transpile and execute the actual screen with every native/network edge mocked. */
function loadScreen(owner: string, deps: {
  fetchVoteStatus: ReturnType<typeof vi.fn>;
  syncVoteMark: ReturnType<typeof vi.fn>;
  submitVote: ReturnType<typeof vi.fn>;
}) {
  const harness = createHarness();
  const reactModule = { __esModule: true, default: harness.api, ...harness.api };
  const bill = { status: "ACTIVE", source: "PARLIAMENT", title_el: "Νόμος Τ" };
  const fetchMock = vi.fn(async () => ({ ok: true, json: async () => bill }));
  const requireMock = vi.fn((id: string): unknown => {
    if (id === "react") return reactModule;
    if (id === "react-native") {
      return {
        View: "View", Text: "Text", TouchableOpacity: "TouchableOpacity", ScrollView: "ScrollView",
        ActivityIndicator: "ActivityIndicator", StyleSheet: { create: (s: unknown) => s },
        Alert: { alert: vi.fn() }, Share: { share: vi.fn() }, Linking: { openURL: vi.fn() },
      };
    }
    if (id === "expo-local-authentication") return { authenticateAsync: vi.fn(), hasHardwareAsync: vi.fn() };
    if (id === "../lib/crypto-native") {
      return {
        loadKeypair: vi.fn(async () => ({ privateKeyHex: `sk-${owner}`, publicKeyHex: `pk-${owner}` })),
        loadNullifier: vi.fn(async () => `nul-${owner}`),
        signVote: vi.fn(() => "sig"),
        signVoteStatusRead: vi.fn(() => `rsig-${owner}`),
        verifyVote: vi.fn(),
      };
    }
    if (id === "../lib/api") {
      return {
        submitVote: deps.submitVote,
        correctVote: vi.fn(),
        fetchVoteStatus: deps.fetchVoteStatus,
        fetchZkStatus: vi.fn(async () => null),
        fetchZkScopeStatus: vi.fn(async () => null),
      };
    }
    if (id === "../lib/demo") return { isDemoMode: () => false };
    if (id === "../theme") return { colors };
    if (id === "../lib/zkCanaryFlow") {
      return {
        submitZkOptInForBill: vi.fn(),
        submitZkVoteWithPublishedRoot: vi.fn(),
        verifyZkVoteWithPublishedRoot: vi.fn(),
      };
    }
    if (id === "../lib/zkSemaphoreIdentity") return { hasZkSemaphoreIdentity: vi.fn(async () => false) };
    if (id === "../lib/zkPublicVoting") return zkPublicVoting;
    if (id === "../lib/zkPilotError") return zkPilotError;
    if (id === "../lib/vote-marks") return { recordVoteMark: vi.fn(), syncVoteMark: deps.syncVoteMark };
    if (id === "../lib/vote-success") return voteSuccess;
    if (id === "../lib/source-resolver") return sourceResolver;
    throw new Error(`Unexpected module ${id}`);
  });
  const source = readFileSync(new URL("./VoteScreen.tsx", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
      jsx: ts.JsxEmit.React,
    },
  }).outputText;
  const exports: Record<string, any> = {};
  vm.runInNewContext(compiled, {
    exports, require: requireMock, console, fetch: fetchMock, setInterval, clearInterval,
    process: { env: { EXPO_PUBLIC_API_URL: "http://api.t" } },
  });
  const Screen = exports.default as (p: unknown) => El;
  const props = { route: { params: { billId: "b-1", billTitle: "Τ" } }, navigation: { navigate: vi.fn() } };
  const screen = harness.mount(() => Screen(props));
  return { harness, screen };
}

async function flush() {
  for (let i = 0; i < 200; i += 1) await Promise.resolve();
}

function findAll(node: unknown, type: string): El[] {
  const out: El[] = [];
  const walk = (n: unknown) => {
    if (Array.isArray(n)) { n.forEach(walk); return; }
    if (!n || typeof n !== "object") return;
    const el = n as El;
    if (el.type !== undefined && el.props) {
      if (el.type === type) out.push(el);
      walk(el.props.children);
    }
  };
  walk(node);
  return out;
}

function textContent(node: unknown): string {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(textContent).join("");
  if (node && typeof node === "object" && (node as El).props) return textContent((node as El).props.children);
  return "";
}

describe("VoteScreen vote-status owner isolation", () => {
  it("ignores owner A's late status after cleanup while a fresh owner-B screen stays eligible", async () => {
    const statusA = deferred<Status>();
    const statusB = deferred<Status>();
    const fetchVoteStatus = vi.fn((nullifier: string) =>
      nullifier === "nul-A" ? statusA.promise : statusB.promise);
    const syncVoteMark = vi.fn(async (_billId: string, _status: Status, _nullifier: string) => {});
    const submitVote = vi.fn();
    const deps = { fetchVoteStatus, syncVoteMark, submitVote };

    const a = loadScreen("A", deps);
    await flush();
    expect(fetchVoteStatus).toHaveBeenCalledTimes(1);
    expect(fetchVoteStatus.mock.calls[0][0]).toBe("nul-A");
    a.screen.unmount();
    const rendersA = a.harness.renderCount();

    const b = loadScreen("B", deps);
    await flush();
    expect(fetchVoteStatus.mock.calls[1][0]).toBe("nul-B");
    const bResponse: Status = { has_voted: false, is_correction: false, vote: null };
    statusB.resolve(bResponse);
    await flush();

    // Late A response carries every field the screen would write.
    statusA.resolve({ has_voted: true, is_correction: true, vote: "NO" });
    await flush();

    expect(syncVoteMark).toHaveBeenCalledTimes(1);
    expect(syncVoteMark).toHaveBeenCalledWith("b-1", bResponse, "nul-B");
    expect(syncVoteMark.mock.calls.some(call => call[2] === "nul-A")).toBe(false);
    expect(a.harness.lateSets()).toBe(0);
    expect(a.harness.renderCount()).toBe(rendersA);

    const tree = b.screen.tree();
    expect(findAll(tree, "Text").some(t =>
      textContent(t) === "Επιλέξτε την ψήφο σας. Απαιτείται βιομετρική πιστοποίηση.")).toBe(true);
    const voteButtons = findAll(tree, "TouchableOpacity").filter(btn =>
      ["ΝΑΙ", "ΟΧΙ", "ΑΠΟΧΗ"].some(label => textContent(btn).includes(label)) && "disabled" in btn.props);
    expect(voteButtons.map(btn => textContent(btn).replace(/[^Α-Ω]/g, ""))).toEqual(["ΝΑΙ", "ΟΧΙ", "ΑΠΟΧΗ"]);
    for (const btn of voteButtons) expect(btn.props.disabled).toBe(false);
    expect(b.harness.lateSets()).toBe(0);
    expect(submitVote).not.toHaveBeenCalled();
  });
});
