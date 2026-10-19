import { afterEach, expect, it, vi } from "vitest";

type RuntimeRule = {
  urlPattern: RegExp | ((args: { url: URL; request: { destination: string } }) => boolean);
};
type PwaOptions = {
  cacheStartUrl: boolean; dynamicStartUrl: boolean; cacheOnFrontEndNav: boolean;
  publicExcludes: string[];
  workboxOptions: { runtimeCaching: RuntimeRule[] };
};
const captured = vi.hoisted(() => ({ options: undefined as PwaOptions | undefined }));
vi.mock("@ducanh2912/next-pwa", () => ({ default: (options: PwaOptions) => {
  captured.options = options;
  return (config: object) => config;
} }));
vi.mock("next-intl/plugin", () => ({ default: () => (config: object) => config }));
import "../next.config.mjs";

afterEach(() => vi.unstubAllGlobals());

it("PWA never caches nonce-bearing navigation or Flight responses", () => {
  const options = captured.options!;
  expect(options.cacheStartUrl).toBe(false);
  expect(options.dynamicStartUrl).toBe(false);
  expect(options.cacheOnFrontEndNav).toBe(false);
  expect(options.publicExcludes).toContain("!**/*.html");
  // The plugin reads runtimeCaching only inside workboxOptions.
  expect(options).not.toHaveProperty("runtimeCaching");
  const rule = options.workboxOptions.runtimeCaching.find(rule => typeof rule.urlPattern === "function")!;
  const matches = rule.urlPattern as Exclude<RuntimeRule["urlPattern"], RegExp>;
  vi.stubGlobal("self", { location: { origin: "https://ekklesia.gr" } });
  for (const destination of ["document", "", "iframe"]) {
    expect(matches({ url: new URL("https://ekklesia.gr/en/bills"), request: { destination } })).toBe(false);
  }
  for (const destination of ["script", "style", "image", "font"]) {
    expect(matches({ url: new URL("https://ekklesia.gr/assets/file"), request: { destination } })).toBe(true);
    expect(matches({ url: new URL("https://elsewhere.invalid/file"), request: { destination } })).toBe(false);
  }
});
