import { expect, it, vi } from "vitest";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { generateSW } from "workbox-build";

type RuntimeRule = { urlPattern: RegExp; handler: "NetworkFirst" | "StaleWhileRevalidate" };
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
import nextConfig from "../next.config.mjs";
import { LEGACY_CSP } from "./lib/csp";

it("keeps one legacy response fallback for runtime CSP_ENFORCE=false rollback", async () => {
  const rules = await nextConfig.headers!();
  const rule = rules.find(rule => rule.source === "/:path*")!;
  expect(rule.headers.filter(header => header.key.toLowerCase() === "content-security-policy"))
    .toEqual([{ key: "Content-Security-Policy", value: LEGACY_CSP }]);
  expect(rule.headers.some(header => header.key.toLowerCase() === "content-security-policy-report-only")).toBe(false);
});

it("PWA caches static file paths and excludes navigation/Flight URLs", () => {
  const options = captured.options!;
  expect(options.cacheStartUrl).toBe(false);
  expect(options.dynamicStartUrl).toBe(false);
  expect(options.cacheOnFrontEndNav).toBe(false);
  expect(options.publicExcludes).toContain("!**/*.html");
  expect(options).not.toHaveProperty("runtimeCaching");
  const pattern = options.workboxOptions.runtimeCaching[1].urlPattern;
  expect(pattern).toBeInstanceOf(RegExp);
  for (const path of ["/en/bills", "/el/bills/public.js", "/en/bills?_rsc=a", "/index.html", "/assets/page.html", "/_next/data/id.json", "/assets/file.js/extra"]) {
    expect(pattern.test("https://ekklesia.gr" + path)).toBe(false);
  }
  for (const path of ["/assets/js/events.js", "/assets/site.css", "/assets/font.woff2", "/_next/static/chunks/app.js?v=1"]) {
    expect(pattern.test("https://ekklesia.gr" + path)).toBe(true);
    expect(pattern.test("https://elsewhere.invalid" + path)).toBe(false);
  }
});

it("the actual Workbox generateSW schema compiles every runtime caching rule", async () => {
  const dir = await mkdtemp(join(tmpdir(), "t9149-workbox-"));
  try {
    await writeFile(join(dir, "fixture.js"), "/* fixture */");
    const result = await generateSW({ ...captured.options!.workboxOptions,
      mode: "development", globDirectory: dir, globPatterns: ["fixture.js"], swDest: join(dir, "sw.js") });
    expect(result.warnings).toEqual([]);
    const sw = await readFile(join(dir, "sw.js"), "utf8");
    expect(sw).toContain("api-cache");
    expect(sw).toContain("static-cache");
    expect(sw).toContain("registerRoute");
  } finally { await rm(dir, { recursive: true, force: true }); }
});
