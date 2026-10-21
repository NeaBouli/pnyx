import { readFileSync } from "node:fs";
import vm from "node:vm";
import { URL } from "node:url";
import ts from "typescript";
import { describe, expect, it, vi } from "vitest";
import { colors } from "../theme";
import * as tabBarLayout from "./tab-bar-layout";

type El = { type: unknown; props: Record<string, any> };

// Vendor icon wrapper height (bottom-tabs TabBarIcon ICON_SIZE_TALL, GH-298 map H9).
const ICON_SLOT_TALL = 28;

/**
 * Transpile and execute the real navigation module with stubbed React,
 * React Native and navigators, then pull `TabNavigator` out of the root
 * stack's "Tabs" screen so its `screenOptions` can be inspected directly.
 */
function loadTabNavigator({ fontScale = 1, width = 360, height = 800, bottomInset = 0 } = {}): El {
  const react = {
    useState: (_init: unknown) => [false, () => {}],
    useEffect: () => {},
    createElement(type: unknown, props?: Record<string, unknown> | null, ...children: unknown[]) {
      return { type, props: { ...(props ?? {}), children } };
    },
  };
  const requireMock = vi.fn((id: string): unknown => {
    if (id === "react") return { __esModule: true, default: react, ...react };
    if (id === "react-native") {
      return {
        Text: "Text", View: "View", ActivityIndicator: "ActivityIndicator",
        useWindowDimensions: () => ({ fontScale, width, height, scale: 3 }),
      };
    }
    if (id === "react-native-safe-area-context") {
      return { useSafeAreaInsets: () => ({ top: 0, bottom: bottomInset, left: 0, right: 0 }) };
    }
    if (id === "@react-navigation/native") return { NavigationContainer: "NavigationContainer" };
    if (id === "@react-navigation/stack") {
      return { createStackNavigator: () => ({ Navigator: "Stack.Navigator", Screen: "Stack.Screen" }) };
    }
    if (id === "@react-navigation/bottom-tabs") {
      return { createBottomTabNavigator: () => ({ Navigator: "Tab.Navigator", Screen: "Tab.Screen" }) };
    }
    if (id === "expo-secure-store") return { getItemAsync: async () => null };
    if (id === "../theme") return { colors };
    if (id === "./linking") return { linking: { prefixes: [], config: { screens: {} } } };
    if (id === "./tab-bar-layout") return tabBarLayout;
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

  it.each(["below-icon", "beside-icon"])("configures active/inactive colors and visible labels (%s)", position => {
    for (const e of EXPECTED) {
      const opts = optionsFor(e.name);
      expect(opts.tabBarActiveTintColor).toBe(colors.tabBarActive);
      expect(opts.tabBarInactiveTintColor).toBe(colors.tabBarInactive);
      expect(opts.tabBarShowLabel).not.toBe(false);
      expect(opts.tabBarStyle).toEqual({ backgroundColor: colors.tabBarBg, borderTopColor: colors.border, height: 56 });
      for (const state of [
        { color: colors.tabBarActive, focused: true },
        { color: colors.tabBarInactive, focused: false },
      ]) {
        const label = opts.tabBarLabel({ ...state, position, children: e.title });
        expect(label.props.style.color).toBe(state.color);
      }
    }
  });

  it.each(["below-icon", "beside-icon"])("configures scalable single-line labels and fit-to-size props (%s)", position => {
    for (const e of EXPECTED) {
      const label = optionsFor(e.name).tabBarLabel({ color: "#000", focused: false, position, children: e.title });
      expect(label.type).toBe("Text");
      expect(label.props.allowFontScaling).not.toBe(false);
      expect(label.props.maxFontSizeMultiplier).toBe(1.4);
      expect(label.props.numberOfLines).toBe(1);
      expect(label.props.adjustsFontSizeToFit).toBe(true);
      expect(label.props.ellipsizeMode).toBe("tail");
      expect(label.props.minimumFontScale).toBeGreaterThanOrEqual(0.75);
      expect(label.props.minimumFontScale).toBeLessThan(1);
      expect(label.props.style.flexShrink).toBe(1);
      expect(label.props.style.maxWidth).toBe("100%");
      expect(label.props.style.marginStart).toBe(position === "beside-icon" ? 5 : 0);
    }
  });

  it("keeps navigator buttons and safe-area handling, with full accessibility labels and minimum touch targets", () => {
    // Configuration delegation only: this does not measure native touch targets
    // or prove taps/layout at system font scale 1.8 or width greater than height.
    expect(tabNavigator.type).toBe("Tab.Navigator");
    expect(tabNavigator.props.tabBar).toBeUndefined();
    expect(tabNavigator.props.safeAreaInsets).toBeUndefined();
    for (const e of EXPECTED) {
      const opts = optionsFor(e.name);
      expect(opts.tabBarButton).toBeUndefined();
      expect(opts.tabBarAccessibilityLabel).toBe(e.title);
      expect(opts.tabBarItemStyle).toEqual({ minWidth: 48, minHeight: 48 });
      expect(opts.safeAreaInsets).toBeUndefined();
    }
  });

  it("caps emoji scaling locally and sizes the graphic from the navigator size", () => {
    for (const e of EXPECTED) {
      for (const size of [25, 18, 40]) {
        const icon = optionsFor(e.name).tabBarIcon({ focused: false, color: "#000", size });
        expect(icon.type).toBe("Text");
        expect(textContent(icon)).toBe(e.icon);
        expect(icon.props.allowFontScaling).not.toBe(false);
        expect(icon.props.maxFontSizeMultiplier).toBe(1.4);
        expect(icon.props.numberOfLines).toBe(1);
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

  it.each([1, 1.3, 1.8].flatMap(fontScale => [0, 24].flatMap(bottomInset => [
    { fontScale, bottomInset, width: 360, height: 800, position: "below-icon" },
    { fontScale, bottomInset, width: 800, height: 360, position: "beside-icon" },
  ])))("applies scale $fontScale and inset $bottomInset at $width x $height", layout => {
    const navigator = loadTabNavigator(layout);
    const metrics = tabBarLayout.getTabBarMetrics(layout.fontScale, layout.bottomInset);
    const scale = Math.min(layout.fontScale, 1.4);
    for (const e of EXPECTED) {
      const opts = navigator.props.screenOptions({ route: { name: e.name } });
      expect(opts.tabBarStyle.height).toBe(metrics.height);
      expect(opts.tabBarStyle.height - layout.bottomInset - 1).toBeGreaterThanOrEqual(48);
      expect(opts.tabBarStyle.paddingBottom).toBeUndefined();
      expect(opts.tabBarLabelPosition).toBe(layout.position);
      expect(opts.tabBarIconStyle).toEqual({ width: metrics.iconWidth, height: metrics.iconHeight });
      const icon = opts.tabBarIcon({ focused: false, color: "#000", size: 25 });
      expect(icon.props.style.lineHeight * scale).toBeLessThanOrEqual(opts.tabBarIconStyle.height);
    }
  });
});
