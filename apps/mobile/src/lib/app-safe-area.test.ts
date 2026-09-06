import { readFileSync } from "node:fs";
import { URL } from "node:url";
import vm from "node:vm";
import ts from "typescript";
import { expect, it } from "vitest";

it("consumes only the top system inset before banners and gives navigation a relative frame", () => {
  const element = (type: unknown, props: Record<string, any>) => ({ type, props });
  const exports: Record<string, any> = {};
  const code = ts.transpileModule(readFileSync(new URL("../../App.tsx", import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  vm.runInNewContext(code, { exports, require: (id: string) => {
    if (id === "react/jsx-runtime") return { jsx: element, jsxs: element };
    if (id === "react") return { useEffect: () => {} };
    if (id === "react-native") return {};
    if (id === "expo-status-bar") return { StatusBar: "StatusBar" };
    if (id === "react-native-safe-area-context") return { SafeAreaProvider: "Provider", SafeAreaView: "SafeView" };
    if (id === "./src/navigation") return { default: "Navigation" };
    if (id === "./src/theme") return { colors: { headerBg: "#123456" } };
    if (id === "./src/lib/notifications") return {};
    throw new Error(`Unexpected import ${id}`);
  } });
  const tree = exports.default();
  expect(tree.type).toBe("Provider");
  const safe = tree.props.children[1];
  expect(safe.type).toBe("SafeView");
  expect([...safe.props.edges]).toEqual(["top"]);
  expect(safe.props.style.flex).toBe(1);
  expect(safe.props.children.type).toBe("Provider");
  expect(safe.props.children.props.children.type).toBe("Navigation");
});
