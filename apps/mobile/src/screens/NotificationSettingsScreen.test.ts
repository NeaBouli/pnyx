import { readFileSync } from "node:fs";
import vm from "node:vm";
import { URL } from "node:url";
import ts from "typescript";
import { describe, expect, it, vi } from "vitest";
import { colors } from "../theme";

const MASTER_KEY = "push_master";

type El = { type: unknown; props: Record<string, any> };

/**
 * Minimal React stub (useState/useEffect/useRef/useCallback/createElement)
 * plus a synchronous render loop, so the REAL screen component executes in a
 * vm context without pulling in react-native. setState re-renders
 * synchronously; useEffect/useCallback honor their dependency arrays;
 * setState after unmount throws, which makes the screen's mounted guards
 * observable.
 */
function createHarness() {
  const stateSlots: unknown[] = [];
  const refSlots: { current: unknown }[] = [];
  const callbackSlots: { deps: unknown[] | undefined; fn: unknown }[] = [];
  const effectSlots: ({ deps: unknown[] | undefined; cleanup?: unknown } | undefined)[] = [];
  let stateIdx = 0;
  let refIdx = 0;
  let cbIdx = 0;
  let effIdx = 0;
  let component: (() => El) | null = null;
  let tree: El | null = null;
  let alive = false;
  let renders = 0;
  let pendingEffects: { i: number; fn: () => unknown; deps: unknown[] | undefined }[] | null = null;

  function depsChanged(prev: unknown[] | undefined, next: unknown[] | undefined): boolean {
    if (!prev || !next) return true;
    return prev.length !== next.length || next.some((d, i) => !Object.is(d, prev[i]));
  }

  function render() {
    if (!component) return;
    stateIdx = refIdx = cbIdx = effIdx = 0;
    renders += 1;
    const scheduled: { i: number; fn: () => unknown; deps: unknown[] | undefined }[] = [];
    pendingEffects = scheduled;
    tree = component();
    pendingEffects = null;
    for (const p of scheduled) {
      // Register the slot BEFORE running the effect: an effect that
      // synchronously setStates (e.g. `load` marking loading=true) triggers
      // a re-entrant render, which must observe this effect as already run.
      const slot: { deps: unknown[] | undefined; cleanup?: unknown } = { deps: p.deps };
      effectSlots[p.i] = slot;
      slot.cleanup = p.fn();
    }
  }

  const api = {
    useState(init: unknown) {
      const i = stateIdx++;
      if (!(i in stateSlots)) {
        stateSlots[i] = typeof init === "function" ? (init as () => unknown)() : init;
      }
      const set = (v: unknown) => {
        if (!alive) throw new Error("setState after unmount");
        stateSlots[i] = typeof v === "function" ? (v as (p: unknown) => unknown)(stateSlots[i]) : v;
        render();
      };
      return [stateSlots[i], set];
    },
    useEffect(fn: () => unknown, deps?: unknown[]) {
      const i = effIdx++;
      const prev = effectSlots[i];
      if (prev && !depsChanged(prev.deps, deps)) return;
      if (prev && typeof prev.cleanup === "function") (prev.cleanup as () => void)();
      if (pendingEffects) pendingEffects.push({ i, fn, deps });
    },
    useRef(init: unknown) {
      const i = refIdx++;
      if (!(i in refSlots)) refSlots[i] = { current: init };
      return refSlots[i];
    },
    useCallback(fn: unknown, deps?: unknown[]) {
      const i = cbIdx++;
      const prev = callbackSlots[i];
      if (prev && !depsChanged(prev.deps, deps)) return prev.fn;
      callbackSlots[i] = { deps, fn };
      return fn;
    },
    createElement(type: unknown, props?: Record<string, unknown> | null, ...children: unknown[]) {
      return { type, props: { ...(props ?? {}), children } };
    },
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

  return { api, mount, renderCount: () => renders };
}

function createStorage(initial: Record<string, string> = {}) {
  const data = new Map<string, string>(Object.entries(initial));
  return {
    data,
    getItemAsync: vi.fn(async (key: string) => data.get(key) ?? null),
    setItemAsync: vi.fn(async (key: string, value: string) => { data.set(key, value); }),
  };
}

/** Transpile and execute the actual screen with stubbed native modules. */
function loadScreen(storage: ReturnType<typeof createStorage>, acks?: {
  markAll?: ReturnType<typeof vi.fn>;
  markCategory?: ReturnType<typeof vi.fn>;
}) {
  const harness = createHarness();
  const markAll = acks?.markAll ?? vi.fn(async () => {});
  const markCategory = acks?.markCategory ?? vi.fn(async (_key: string) => {});
  const reactModule = { __esModule: true, default: harness.api, ...harness.api };
  const requireMock = vi.fn((id: string): unknown => {
    if (id === "react") return reactModule;
    if (id === "react-native") {
      return {
        View: "View",
        Text: "Text",
        Switch: "Switch",
        ScrollView: "ScrollView",
        TouchableOpacity: "TouchableOpacity",
        StyleSheet: { create: (styles: unknown) => styles },
      };
    }
    if (id === "expo-secure-store") return storage;
    if (id === "../theme") return { colors };
    if (id === "../lib/notifications") {
      return {
        markAllNotificationsRead: markAll,
        markNotificationCategoryRead: markCategory,
      };
    }
    throw new Error(`Unexpected module ${id}`);
  });
  const source = readFileSync(new URL("./NotificationSettingsScreen.tsx", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
      jsx: ts.JsxEmit.React,
    },
  }).outputText;
  const exports: Record<string, any> = {};
  vm.runInNewContext(compiled, { exports, require: requireMock, console });
  const screen = harness.mount(exports.default as () => El);
  return { harness, screen, markAll, markCategory };
}

/** Drain the microtask queue so pending async screen work settles. */
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
  if (node && typeof node === "object") {
    const el = node as El;
    if (el.props) return textContent(el.props.children);
  }
  return "";
}

const switches = (tree: El) => findAll(tree, "Switch");
const retryButtons = (tree: El) => findAll(tree, "TouchableOpacity");
const alerts = (tree: El) =>
  findAll(tree, "Text").filter(t => t.props.accessibilityRole === "alert");

describe("NotificationSettingsScreen hydration", () => {
  it("keeps every switch disabled until hydration completes, then applies persisted values", async () => {
    const storage = createStorage({ push_vote_open: "false" });
    const { screen } = loadScreen(storage);

    // Before hydration resolves, the switches render disabled (loaded=false).
    expect(switches(screen.tree()).length).toBeGreaterThan(1);
    for (const sw of switches(screen.tree())) {
      expect(sw.props.disabled).toBe(true);
    }

    await flush();

    const [master, ...categories] = switches(screen.tree());
    expect(master.props.disabled).toBe(false);
    expect(master.props.value).toBe(true); // missing key defaults to on
    expect(categories[0].props.value).toBe(false); // persisted opt-out applied
    expect(categories[0].props.disabled).toBe(false);
    expect(categories[1].props.value).toBe(true);
    expect(categories[1].props.disabled).toBe(false);
    expect(retryButtons(screen.tree())).toHaveLength(0);
  });

  it("stays disabled after a failed load and recovers through the explicit retry", async () => {
    const storage = createStorage();
    storage.getItemAsync.mockRejectedValueOnce(new Error("native read failure"));
    const { screen } = loadScreen(storage);
    await flush();

    for (const sw of switches(screen.tree())) {
      expect(sw.props.disabled).toBe(true);
    }
    const retries = retryButtons(screen.tree());
    expect(retries).toHaveLength(1);
    expect(textContent(retries[0])).toContain("Δοκιμάστε ξανά");
    expect(retries[0].props.disabled).toBe(false);

    await retries[0].props.onPress();
    await flush();

    const [master, voteOpen] = switches(screen.tree());
    expect(master.props.disabled).toBe(false);
    expect(voteOpen.props.disabled).toBe(false);
    expect(retryButtons(screen.tree())).toHaveLength(0);
  });

  it("never updates state after unmount during hydration", async () => {
    const resolvers: ((v: string | null) => void)[] = [];
    const storage = createStorage();
    storage.getItemAsync.mockImplementation(
      () => new Promise<string | null>(resolve => { resolvers.push(resolve); }),
    );
    const { screen, harness } = loadScreen(storage);
    screen.unmount();
    const before = harness.renderCount();

    // Drive the pending hydration to completion after unmount: every
    // post-await state update must be skipped by the mounted guard.
    for (let round = 0; round < 10; round += 1) {
      for (const resolve of resolvers.splice(0)) resolve(null);
      await flush();
    }
    expect(harness.renderCount()).toBe(before);
  });
});

describe("NotificationSettingsScreen opt-out acknowledgement", () => {
  it("allows re-enabling after repeated acknowledgement failure and remount without replaying stale scope", async () => {
    const storage = createStorage({ push_master: "false" });
    const unavailable = vi.fn().mockRejectedValue(new Error("ledger unavailable"));
    const first = loadScreen(storage, { markAll: unavailable });
    await flush();
    first.screen.unmount();
    const { screen, markAll } = loadScreen(storage, { markAll: unavailable });
    await flush();
    const staleRetry = retryButtons(screen.tree())[0].props.onPress;
    expect(switches(screen.tree())[0].props.disabled).toBe(false);
    const calls = markAll.mock.calls.length;
    await switches(screen.tree())[0].props.onValueChange(true);
    await staleRetry();
    expect(storage.data.get(MASTER_KEY)).toBe("true");
    expect(markAll).toHaveBeenCalledTimes(calls);
    expect(retryButtons(screen.tree())).toHaveLength(0);
  });

  it("recomputes pending categories after re-enable and still permits another opt-out", async () => {
    const storage = createStorage({ push_vote_open: "false", push_vote_result: "false" });
    const markCategory = vi.fn().mockRejectedValue(new Error("ledger unavailable"));
    const { screen } = loadScreen(storage, { markCategory });
    await flush();
    expect(switches(screen.tree())[1].props.disabled).toBe(false);
    markCategory.mockClear();
    await switches(screen.tree())[1].props.onValueChange(true);
    expect(markCategory.mock.calls.map(call => call[0])).toEqual(["push_vote_result", "push_vote_result"]);
    markCategory.mockResolvedValue(undefined);
    await switches(screen.tree())[2].props.onValueChange(false);
    expect(storage.data.get("push_vote_open")).toBe("true");
    expect(storage.data.get("push_vote_24h")).toBe("false");
    expect(markCategory.mock.calls.slice(2).map(call => call[0])).toEqual(["push_vote_24h", "push_vote_result"]);
  });
  it("recovers pending opt-outs on a fresh screen without acknowledging enabled categories", async () => {
    const storage = createStorage({ push_vote_open: "false", push_vote_result: "false" });
    const failed = loadScreen(storage, { markCategory: vi.fn().mockRejectedValue(new Error("unavailable")) });
    await flush();
    expect(retryButtons(failed.screen.tree())).toHaveLength(1);
    failed.screen.unmount();
    const recovered = loadScreen(storage);
    await flush();
    expect(recovered.markCategory.mock.calls.map(call => call[0])).toEqual(["push_vote_open", "push_vote_result"]);
    expect(recovered.markAll).not.toHaveBeenCalled();
    expect(retryButtons(recovered.screen.tree())).toHaveLength(0);
    expect(storage.setItemAsync).not.toHaveBeenCalled();
    expect(switches(recovered.screen.tree())[0].props.disabled).toBe(false);
  });

  it("finishes acknowledgement after unmount and rejects duplicate in-flight toggles", async () => {
    const storage = createStorage();
    const { screen, markAll, harness } = loadScreen(storage);
    await flush();
    let finish!: () => void;
    storage.setItemAsync.mockImplementationOnce((key, value) => new Promise<void>(resolve => {
      finish = () => { storage.data.set(key, value); resolve(); };
    }));
    const master = switches(screen.tree())[0];
    const pending = master.props.onValueChange(false);
    await master.props.onValueChange(true);
    expect(storage.setItemAsync).toHaveBeenCalledTimes(1);
    screen.unmount();
    const renders = harness.renderCount();
    finish();
    await pending;
    expect(markAll).toHaveBeenCalledTimes(1);
    expect(storage.data.get(MASTER_KEY)).toBe("false");
    expect(harness.renderCount()).toBe(renders);
  });

  it("recovers a persisted master opt-out after remount", async () => {
    const storage = createStorage({ push_master: "false" });
    const { screen, markAll, markCategory } = loadScreen(storage);
    await flush();
    expect(markAll).toHaveBeenCalledTimes(1);
    expect(markCategory).not.toHaveBeenCalled();
    expect(switches(screen.tree())[0].props.value).toBe(false);
    expect(storage.setItemAsync).not.toHaveBeenCalled();
  });
  it("preserves a saved master opt-out when acknowledgement fails twice, then completes on manual retry", async () => {
    const storage = createStorage();
    const { screen, markAll, markCategory } = loadScreen(storage);
    await flush();

    markAll.mockRejectedValue(new Error("ledger write failed"));
    const [master] = switches(screen.tree());
    await master.props.onValueChange(false);

    // The opt-out persisted and stays persisted — it is never re-enabled.
    expect(storage.setItemAsync).toHaveBeenCalledWith(MASTER_KEY, "false");
    expect(storage.data.get(MASTER_KEY)).toBe("false");
    // Exactly one automatic retry followed the initial attempt.
    expect(markAll).toHaveBeenCalledTimes(2);
    expect(markCategory).not.toHaveBeenCalled();

    const afterFail = switches(screen.tree());
    expect(afterFail[0].props.value).toBe(false);
    // Master remains usable; categories are disabled only by the saved opt-out.
    expect(afterFail[0].props.disabled).toBe(false);
    for (const sw of afterFail.slice(1)) expect(sw.props.disabled).toBe(true);
    const ackRetries = retryButtons(screen.tree());
    expect(ackRetries).toHaveLength(1);
    expect(textContent(ackRetries[0])).toContain("Επανάληψη");

    markAll.mockResolvedValue(undefined);
    await ackRetries[0].props.onPress();
    await flush();

    expect(markAll).toHaveBeenCalledTimes(3);
    expect(retryButtons(screen.tree())).toHaveLength(0);
    const final = switches(screen.tree());
    expect(final[0].props.value).toBe(false); // opt-out still intact
    expect(final[0].props.disabled).toBe(false);
    // Categories remain disabled only because the master switch is off.
    expect(final[1].props.disabled).toBe(true);
  });

  it("preserves a saved category opt-out when its acknowledgement fails, with automatic and manual retry", async () => {
    const storage = createStorage();
    const { screen, markAll, markCategory } = loadScreen(storage);
    await flush();

    markCategory.mockRejectedValue(new Error("ledger write failed"));
    const [, voteOpen] = switches(screen.tree());
    await voteOpen.props.onValueChange(false);

    expect(storage.setItemAsync).toHaveBeenCalledWith("push_vote_open", "false");
    expect(storage.data.get("push_vote_open")).toBe("false");
    expect(markCategory).toHaveBeenCalledTimes(2);
    expect(markCategory).toHaveBeenCalledWith("push_vote_open");
    expect(markAll).not.toHaveBeenCalled();

    const afterFail = switches(screen.tree());
    expect(afterFail[1].props.value).toBe(false);
    for (const sw of afterFail) expect(sw.props.disabled).toBe(false);
    const ackRetries = retryButtons(screen.tree());
    expect(ackRetries).toHaveLength(1);

    markCategory.mockResolvedValue(undefined);
    await ackRetries[0].props.onPress();
    await flush();

    expect(markCategory).toHaveBeenCalledTimes(3);
    expect(retryButtons(screen.tree())).toHaveLength(0);
    const final = switches(screen.tree());
    expect(final[0].props.disabled).toBe(false);
    expect(final[1].props.disabled).toBe(false);
    expect(final[1].props.value).toBe(false); // saved opt-out preserved
  });
});

describe("NotificationSettingsScreen persistence failures", () => {
  it("leaves the previous master state untouched when persisting fails", async () => {
    const storage = createStorage();
    const { screen, markAll } = loadScreen(storage);
    await flush();

    storage.setItemAsync.mockRejectedValueOnce(new Error("native write failure"));
    const [master] = switches(screen.tree());
    await master.props.onValueChange(false);

    expect(storage.data.has(MASTER_KEY)).toBe(false);
    expect(markAll).not.toHaveBeenCalled();
    const after = switches(screen.tree());
    expect(after[0].props.value).toBe(true); // old state preserved
    expect(after[0].props.disabled).toBe(false);
    expect(
      alerts(screen.tree()).some(t => textContent(t).includes("Αδυναμία αποθήκευσης")),
    ).toBe(true);
  });

  it("leaves the previous category state untouched when persisting fails", async () => {
    const storage = createStorage();
    const { screen, markCategory } = loadScreen(storage);
    await flush();

    storage.setItemAsync.mockRejectedValueOnce(new Error("native write failure"));
    const [, voteOpen] = switches(screen.tree());
    await voteOpen.props.onValueChange(false);

    expect(storage.data.has("push_vote_open")).toBe(false);
    expect(markCategory).not.toHaveBeenCalled();
    const after = switches(screen.tree());
    expect(after[1].props.value).toBe(true); // old state preserved
    expect(after[1].props.disabled).toBe(false);
  });
});
