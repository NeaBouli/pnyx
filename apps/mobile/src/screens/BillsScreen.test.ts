import { readFileSync } from "node:fs";
import vm from "node:vm";
import { URL } from "node:url";
import ts from "typescript";
import { describe, expect, it, vi } from "vitest";
import { mergeBillsUnique, prioritizeBillsPage } from "../lib/bill-feed";
import { availableGeographicFilters, scopedBillQuery } from "../lib/bill-scope";
import { colors } from "../theme";

type El = { type: unknown; props: Record<string, any> };
type Bill = { id: string; title_el: string; status: string; source: string };
type Effect = { deps?: unknown[]; cleanup?: unknown };
const LOAD_ERROR = "Δεν ήταν δυνατή η φόρτωση των ψηφοφοριών. Δοκιμάστε ξανά.";

/** Same native-free render pattern as NotificationSettingsScreen.test.ts. */
function createHarness() {
  const states: unknown[] = [];
  const refs: { current: unknown }[] = [];
  const callbacks: { deps?: unknown[]; fn: unknown }[] = [];
  const effects: (Effect | undefined)[] = [];
  let stateIndex = 0;
  let refIndex = 0;
  let callbackIndex = 0;
  let effectIndex = 0;
  let component: (() => El) | undefined;
  let tree: El;
  let pending: { index: number; fn: () => unknown; deps?: unknown[] }[] | undefined;

  const changed = (previous?: unknown[], next?: unknown[]) => !previous || !next
    || previous.length !== next.length
    || next.some((value, index) => !Object.is(value, previous[index]));

  function render() {
    if (!component) return;
    stateIndex = refIndex = callbackIndex = effectIndex = 0;
    const scheduled: NonNullable<typeof pending> = [];
    pending = scheduled;
    tree = component();
    pending = undefined;
    for (const effect of scheduled) {
      // Register before running: an effect can synchronously update state.
      const slot: Effect = { deps: effect.deps };
      effects[effect.index] = slot;
      slot.cleanup = effect.fn();
    }
  }

  const api = {
    useState(initial: unknown) {
      const index = stateIndex++;
      if (!(index in states)) states[index] = typeof initial === "function"
        ? (initial as () => unknown)() : initial;
      const set = (value: unknown) => {
        const next = typeof value === "function"
          ? (value as (previous: unknown) => unknown)(states[index]) : value;
        if (Object.is(states[index], next)) return;
        states[index] = next;
        render();
      };
      return [states[index], set];
    },
    useRef(initial: unknown) {
      const index = refIndex++;
      if (!(index in refs)) refs[index] = { current: initial };
      return refs[index];
    },
    useCallback(fn: unknown, deps?: unknown[]) {
      const index = callbackIndex++;
      if (callbacks[index] && !changed(callbacks[index].deps, deps)) return callbacks[index].fn;
      callbacks[index] = { deps, fn };
      return fn;
    },
    useEffect(fn: () => unknown, deps?: unknown[]) {
      const index = effectIndex++;
      const previous = effects[index];
      if (previous && !changed(previous.deps, deps)) return;
      if (typeof previous?.cleanup === "function") previous.cleanup();
      pending?.push({ index, fn, deps });
    },
    createElement(type: unknown, props?: Record<string, unknown> | null, ...children: unknown[]): El {
      return { type, props: { ...props, children } };
    },
  };

  return {
    api,
    mount(screen: () => El) {
      component = screen;
      render();
      return { tree: () => tree };
    },
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function loadScreen() {
  const harness = createHarness();
  const requests: {
    params: Record<string, unknown>;
    response: ReturnType<typeof deferred<Bill[]>>;
  }[] = [];
  const fetchBills = vi.fn((params: Record<string, unknown>) => {
    const response = deferred<Bill[]>();
    requests.push({ params, response });
    return response.promise;
  });
  const unexpected = () => { throw new Error("Unexpected external or navigation call"); };
  const react = { __esModule: true, default: harness.api, ...harness.api };
  const modules: Record<string, unknown> = {
    react,
    "react-native": {
      ...Object.fromEntries([
        "View", "Text", "FlatList", "TouchableOpacity", "ActivityIndicator", "RefreshControl", "ScrollView",
      ].map(name => [name, name])),
      StyleSheet: { create: (styles: unknown) => styles },
      Share: { share: unexpected },
      Linking: { openURL: unexpected },
    },
    "@react-navigation/native": {
      useNavigation: () => ({ navigate: unexpected }),
      useFocusEffect: (fn: () => unknown) => harness.api.useEffect(fn, [fn]),
    },
    "../lib/api": { fetchBills },
    "../lib/bill-feed": { mergeBillsUnique, prioritizeBillsPage },
    "../lib/bill-scope": { availableGeographicFilters, scopedBillQuery },
    "../lib/bill-scope-storage": {
      loadUserBillScope: vi.fn(async () => ({ periferiaId: null, dimosId: null })),
    },
    "../lib/crypto-native": { isVerified: vi.fn(async () => false) },
    "../lib/vote-marks": { loadVoteMarks: vi.fn(async () => ({})), tileVoteLabel: () => null },
    "../theme": { colors },
    "expo-secure-store": { getItemAsync: unexpected, setItemAsync: unexpected, deleteItemAsync: unexpected },
  };
  const source = readFileSync(new URL("./BillsScreen.tsx", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
      jsx: ts.JsxEmit.React,
    },
  }).outputText;
  const exports: Record<string, unknown> = {};
  vm.runInNewContext(compiled, {
    exports,
    require: (name: string) => {
      if (!(name in modules)) throw new Error(`Unexpected module ${name}`);
      return modules[name];
    },
    console,
  });
  return { screen: harness.mount(exports.default as () => El), fetchBills, requests };
}

type Screen = ReturnType<typeof loadScreen>;

async function flush() {
  for (let index = 0; index < 100; index += 1) await Promise.resolve();
}

function findAll(node: unknown, type: string): El[] {
  if (Array.isArray(node)) return node.flatMap(child => findAll(child, type));
  if (!node || typeof node !== "object") return [];
  const element = node as El;
  if (!element.props) return [];
  return [
    ...(element.type === type ? [element] : []),
    ...findAll(element.props.children, type),
  ];
}

function text(node: unknown): string {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(text).join("");
  if (!node || typeof node !== "object") return "";
  return text((node as El).props?.children);
}

function list(screen: Screen): El {
  const lists = findAll(screen.screen.tree(), "FlatList");
  expect(lists).toHaveLength(1);
  return lists[0];
}

function cardTexts(screen: Screen): string[] {
  const current = list(screen);
  return current.props.data.map((item: Bill) => text(current.props.renderItem({ item })));
}

function ids(screen: Screen): string[] {
  return list(screen).props.data.map((item: Bill) => item.id);
}

function button(screen: Screen, label: string): El {
  const matches = findAll(screen.screen.tree(), "TouchableOpacity").filter(item => text(item) === label);
  expect(matches).toHaveLength(1);
  return matches[0];
}

function errorButtons(screen: Screen): El[] {
  return findAll(screen.screen.tree(), "TouchableOpacity").filter(item => text(item) === LOAD_ERROR);
}

function bill(id: string): Bill {
  return { id, title_el: `Fixture bill ${id}`, status: "ACTIVE", source: "PARLIAMENT" };
}

function finishMixed(screen: Screen, start: number, items: Bill[]) {
  expect(screen.requests.slice(start).map(request => request.params)).toEqual([
    expect.objectContaining({ limit: 20, offset: 0 }),
    expect.objectContaining({ limit: 4, offset: 0, source: "PARLIAMENT" }),
  ]);
  screen.requests[start].response.resolve(items);
  screen.requests[start + 1].response.resolve([]);
}

async function initialList(items: Bill[] = [bill("A")]): Promise<Screen> {
  const screen = loadScreen();
  await flush();
  finishMixed(screen, 0, items);
  await flush();
  expect(ids(screen)).toEqual(items.slice(0, 10).map(item => item.id));
  expect(errorButtons(screen)).toHaveLength(0);
  return screen;
}

describe("BillsScreen fetch failure state", () => {
  it.each(["refresh", "filter"] as const)("clears A after a %s failure and loads B through retry", async trigger => {
    const screen = await initialList();
    expect(cardTexts(screen)[0]).toContain("Fixture bill A");
    const start = screen.requests.length;
    if (trigger === "refresh") list(screen).props.refreshControl.props.onRefresh();
    else button(screen, "Ανακοιν.").props.onPress();
    await flush();
    expect(screen.requests).toHaveLength(start + (trigger === "refresh" ? 2 : 1));
    if (trigger === "filter") expect(screen.requests[start].params.status).toBe("ANNOUNCED");
    screen.requests[start].response.reject(new Error("fixture fetch failure"));
    if (trigger === "refresh") screen.requests[start + 1].response.resolve([]);
    await flush();

    expect(ids(screen)).toEqual([]);
    expect(cardTexts(screen)).toEqual([]);
    expect(text(list(screen).props.ListEmptyComponent)).not.toBe("");
    expect(list(screen).props.refreshControl.props.refreshing).toBe(false);
    expect(errorButtons(screen)).toHaveLength(1);
    const retryStart = screen.requests.length;
    const retry = errorButtons(screen)[0].props.onPress();
    await flush();
    if (trigger === "refresh") finishMixed(screen, retryStart, [bill("B")]);
    else {
      expect(screen.requests).toHaveLength(retryStart + 1);
      expect(screen.requests[retryStart].params.status).toBe("ANNOUNCED");
      screen.requests[retryStart].response.resolve([bill("B")]);
    }
    await retry;
    await flush();
    expect(ids(screen)).toEqual(["B"]);
    expect(cardTexts(screen)[0]).toContain("Fixture bill B");
    expect(cardTexts(screen).join("")).not.toContain("Fixture bill A");
    expect(errorButtons(screen)).toHaveLength(0);
  });

  it.each([0, 1])("ignores an older mixed-fetch error from request %i after B is rendered", async failingRequest => {
    const screen = await initialList();
    const older = screen.requests.length;
    list(screen).props.refreshControl.props.onRefresh();
    await flush();
    expect(screen.requests).toHaveLength(older + 2);
    button(screen, "Ανακοιν.").props.onPress();
    await flush();
    expect(screen.requests).toHaveLength(older + 3);
    screen.requests[older + 2].response.resolve([bill("B")]);
    await flush();
    expect(ids(screen)).toEqual(["B"]);
    expect(cardTexts(screen)[0]).toContain("Fixture bill B");
    expect(errorButtons(screen)).toHaveLength(0);

    screen.requests[older + failingRequest].response.reject(new Error("obsolete fixture failure"));
    screen.requests[older + 1 - failingRequest].response.resolve([]);
    await flush();
    expect(ids(screen)).toEqual(["B"]);
    expect(cardTexts(screen)[0]).toContain("Fixture bill B");
    expect(errorButtons(screen)).toHaveLength(0);
    expect(list(screen).props.refreshControl.props.refreshing).toBe(false);
  });

  it("keeps the current ten cards when pagination fails", async () => {
    const items = Array.from({ length: 11 }, (_, index) => bill(`A-${index}`));
    const screen = await initialList(items);
    const before = cardTexts(screen);
    const footer = list(screen).props.ListFooterComponent as El;
    expect(text(footer)).toBe("Περισσότερα");
    expect(footer.props.disabled).toBe(false);
    const start = screen.requests.length;
    footer.props.onPress();
    await flush();
    expect(screen.requests).toHaveLength(start + 1);
    expect(screen.requests[start].params).toEqual(expect.objectContaining({ limit: 10, offset: 10 }));
    expect(list(screen).props.ListFooterComponent.props.disabled).toBe(true);
    screen.requests[start].response.reject(new Error("fixture pagination failure"));
    await flush();

    expect(ids(screen)).toEqual(items.slice(0, 10).map(item => item.id));
    expect(cardTexts(screen)).toEqual(before);
    expect(errorButtons(screen)).toHaveLength(1);
    expect(list(screen).props.ListFooterComponent.props.disabled).toBe(false);
  });
});
