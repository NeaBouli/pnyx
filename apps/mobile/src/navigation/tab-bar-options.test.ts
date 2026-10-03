import { readFileSync } from "node:fs";
import vm from "node:vm";
import { URL } from "node:url";
import ts from "typescript";
import { describe, expect, it, vi } from "vitest";
import { colors } from "../theme";

type El = { type: unknown; props: Record<string, any> };

// Vendor icon wrapper height (bottom-tabs TabBarIcon ICON_SIZE_TALL, GH-298 map H9).
const ICON_SLOT_TALL = 28;

/**
 * Transpile and execute the real navigation module with stubbed React,
 * React Native and navigators, then pull `TabNavigator` out of the root
 * stack's "Tabs" screen so its `screenOptions` can be inspected directly.
 */
function loadTabNavigator(): El {
  const react = {
    useState: (_init: unknown) => [false, () => {}],
    useEffect: () => {},
    createElement(type: unknown, props?: Record<string, unknown> | null, ...children: unknown[]) {
      return { type, props: { ...(props ?? {}), children } };
    },
  };
  const requireMock = vi.fn((id: string): unknown => {
    if (id === "react") return { __esModule: true, default: react, ...react };
    if (id === "react-native") return { Text: "Text", View: "View", ActivityIndicator: "ActivityIndicator" };
    if (id === "@react-navigation/native") return { NavigationContainer: "NavigationContainer" };
    if (id === "@react-navigation/stack") {
      return { createStackNavigator: () => ({ Navigator: "Stack.Navigator", Screen: "Stack.Screen" }) };
    }
    if (id === "@react-navigation/bottom-tabs") {
      return { createBottomTabNavigator: () => ({ Navigator: "Tab.Navigator", Screen: "Tab.Screen" }) };
    }
    if (id === "expo-secure-store") return { getItemAsync: async () => null };
    if (id === "../theme") return { colors };
    if (id.startsWith("../components/") || id.startsWith("../screens/")) {
      return { __esModule: true, default: id, ChannelNotice: id, MirrorReadOnlyBanner: id, UpdateBanner: id };
    }
    throw new Error(`Unexpected module ${id}`);
  });
  const source = readFileSync(new URL("./index.tsx", import.meta.url), "utf8");
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
  const root = (exports.default as () => El)();
  const tabsScreen = findAll(root, "Stack.Screen").find(s => s.props.name === "Tabs");
  expect(tabsScreen).toBeDefined();
  return (tabsScreen!.props.component as () => El)();
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
  if (node && typeof node === "object") return textContent((node as El).props?.children);
  return "";
}

const tabNavigator = loadTabNavigator();
const tabScreens = findAll(tabNavigator, "Tab.Screen");
const optionsFor = (name: string) => tabNavigator.props.screenOptions({ route: { name } });

const EXPECTED = [
  { name: "Home", title: "εκκλησία", label: "εκκλησία", icon: "🏠" },
  { name: "Bills", title: "Ψηφοφορίες", label: "Ψ/φορία", icon: "🏛️" },
  { name: "Trending", title: "Trending", label: "Trending", icon: "🔥" },
  { name: "MP", title: "Κόμματα", label: "Κόμματα", icon: "📊" },
  { name: "Tickets", title: "POLIS", label: "POLIS", icon: "🎫" },
];

describe("TabNavigator bottom tab options (GH-298)", () => {
  it("keeps the five routes, titles and short labels unchanged", () => {
    expect(tabScreens.map(s => [s.props.name, s.props.options.title])).toEqual(
      EXPECTED.map(e => [e.name, e.title]),
    );
    for (const e of EXPECTED) {
      const label = optionsFor(e.name).tabBarLabel({ color: "#000", focused: false, position: "below-icon", children: e.title });
      expect(textContent(label)).toBe(e.label);
    }
  });

  it("keeps active/inactive colors and never hides the label", () => {
    for (const e of EXPECTED) {
      const opts = optionsFor(e.name);
      expect(opts.tabBarActiveTintColor).toBe(colors.tabBarActive);
      expect(opts.tabBarInactiveTintColor).toBe(colors.tabBarInactive);
      expect(opts.tabBarShowLabel).not.toBe(false);
      expect(opts.tabBarStyle).toEqual({ backgroundColor: colors.tabBarBg, borderTopColor: colors.border });
      const label = opts.tabBarLabel({ color: colors.tabBarActive, focused: true, position: "below-icon", children: e.title });
      expect(label.props.style.color).toBe(colors.tabBarActive);
    }
  });

  it("renders a single-line label that keeps font scaling up to at least 1.8 and fits its column", () => {
    for (const e of EXPECTED) {
      const label = optionsFor(e.name).tabBarLabel({ color: "#000", focused: false, position: "below-icon", children: e.title });
      expect(label.type).toBe("Text");
      expect(label.props.allowFontScaling).not.toBe(false);
      if (label.props.maxFontSizeMultiplier !== undefined) {
        expect(label.props.maxFontSizeMultiplier === 0 || label.props.maxFontSizeMultiplier >= 1.8).toBe(true);
      }
      expect(label.props.numberOfLines).toBe(1);
      expect(label.props.adjustsFontSizeToFit).toBe(true);
      expect(label.props.minimumFontScale).toBeGreaterThanOrEqual(0.75);
      expect(label.props.minimumFontScale).toBeLessThan(1);
    }
  });

  it("sizes the emoji icon from the navigator size as a non-scaling graphic inside the 28dp slot", () => {
    for (const e of EXPECTED) {
      for (const size of [25, 18, 40]) {
        const icon = optionsFor(e.name).tabBarIcon({ focused: false, color: "#000", size });
        expect(icon.type).toBe("Text");
        expect(textContent(icon)).toBe(e.icon);
        expect(icon.props.allowFontScaling).toBe(false);
        const { fontSize, lineHeight } = icon.props.style;
        expect(fontSize).toBeLessThanOrEqual(Math.min(size, ICON_SLOT_TALL));
        expect(lineHeight).toBeLessThanOrEqual(ICON_SLOT_TALL);
        expect(lineHeight).toBeLessThanOrEqual(size);
      }
      // The icon follows the provided size instead of a hard-coded value.
      const small = optionsFor(e.name).tabBarIcon({ focused: false, color: "#000", size: 18 }).props.style.fontSize;
      const regular = optionsFor(e.name).tabBarIcon({ focused: false, color: "#000", size: 25 }).props.style.fontSize;
      expect(small).toBeLessThan(regular);
    }
  });
});
