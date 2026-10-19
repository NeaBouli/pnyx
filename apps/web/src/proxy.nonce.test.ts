import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { NextRequest } from "next/server";
import proxy, { config } from "./proxy";
import { LEGACY_CSP, STATIC_CSP } from "./lib/csp";

const require = createRequire(import.meta.url);
const { getScriptNonceFromHeader } = require("next/dist/server/app-render/get-script-nonce-from-header");
const { createInlinedDataReadableStream } = require("next/dist/server/app-render/use-flight-response");
const testing = require("next/experimental/testing/server");

afterEach(() => vi.unstubAllEnvs());

describe("Next 16 nonce policy through real next-intl middleware", () => {
  it("the Next matcher covers dotted bill identifiers and excludes static assets", () => {
    const matches = testing.unstable_doesProxyMatch ?? testing.unstable_doesMiddlewareMatch;
    for (const url of ["/el/bills/public.id", "/en/bills/public.id", "/en/results"]) {
      expect(matches({ config, nextConfig: {}, url })).toBe(true);
    }
    for (const url of ["/wiki/faq.html", "/assets/js/events.js", "/_next/static/chunk.js"]) {
      expect(matches({ config, nextConfig: {}, url })).toBe(false);
    }
  });

  it.each(["/el/bills", "/en/results", "/en/analytics", "/el/bills/public-id", "/el/bills/public.id", "/el/unknown", "/en/sso-verify"])("forwards matching nonce/CSP and locale for %s", (path) => {
    const response = proxy(new NextRequest(`https://ekklesia.gr${path}`, { headers: {
      "x-nonce": "attacker", "Content-Security-Policy": "script-src 'unsafe-inline'",
      "Content-Security-Policy-Report-Only": "script-src 'nonce-attacker'",
    } }));
    const nonce = response.headers.get("x-middleware-request-x-nonce");
    const policy = response.headers.get("Content-Security-Policy-Report-Only");
    expect(nonce).toMatch(/^[A-Za-z0-9+/]{43}=$/);
    expect(Buffer.from(nonce!, "base64").length).toBe(32);
    expect(response.headers.get("x-middleware-request-content-security-policy")).toBe(policy);
    expect(getScriptNonceFromHeader(policy)).toBe(nonce);
    expect(response.headers.get("x-middleware-request-x-next-intl-locale")).toBe(path.split("/")[1]);
    expect(policy).toBe(STATIC_CSP.replace("script-src 'self'", `script-src 'self' 'nonce-${nonce}'`));
    expect(policy?.split(";").find(directive => directive.trim().startsWith("script-src"))).not.toMatch(/unsafe-inline|unsafe-eval|strict-dynamic|sha256-|attacker/);
    expect(response.headers.get("Content-Security-Policy")).toBe(LEGACY_CSP);
    expect(response.headers.get("cache-control")).toContain("no-store");
    expect(response.headers.get("x-middleware-request-content-security-policy-report-only")).toBeNull();
  });

  it("the Next renderer emits matching nonces on bootstrap and streamed Flight scripts", async () => {
    const response = proxy(new NextRequest("https://ekklesia.gr/el/bills"));
    const nonce = getScriptNonceFromHeader(response.headers.get("x-middleware-request-content-security-policy"));
    const flight = new ReadableStream({ start(controller) {
      controller.enqueue(new TextEncoder().encode('0:"public fixture"\n'));
      controller.close();
    } });
    const html = await new Response(createInlinedDataReadableStream(flight, nonce, null)).text();
    expect(html).toContain("self.__next_f");
    const tags = html.match(/<script[^>]*>/g)!;
    expect(tags.length).toBeGreaterThanOrEqual(2);
    for (const tag of tags) expect(tag).toBe(`<script nonce="${nonce}">`);
  });

  it("uses a fresh nonce for repeated HTML, prefetch and RSC requests", () => {
    const inputs: (HeadersInit | undefined)[] = [undefined, { rsc: "1" }, { "next-router-prefetch": "1" }];
    const nonces = inputs.map(headers => {
      const response = proxy(new NextRequest("https://ekklesia.gr/el/bills", { headers }));
      return response.headers.get("x-middleware-request-x-nonce");
    });
    expect(new Set(nonces).size).toBe(3);
  });

  it("promotes the same candidate while retaining Report-Only", () => {
    vi.stubEnv("CSP_ENFORCE", "true");
    const response = proxy(new NextRequest("https://ekklesia.gr/en/bills"));
    expect(response.headers.get("Content-Security-Policy")).toBe(response.headers.get("Content-Security-Policy-Report-Only"));
    expect(getScriptNonceFromHeader(response.headers.get("Content-Security-Policy"))).toBeTruthy();
  });

  it("preserves static rewrites and locale redirects without attaching a nonce", () => {
    const root = proxy(new NextRequest("https://ekklesia.gr/"));
    expect(root.headers.get("x-middleware-rewrite")).toBe("https://ekklesia.gr/index.html");
    for (const path of ["/tickets/", "/en/community", "/el/wiki/faq"]) {
      const response = proxy(new NextRequest(`https://ekklesia.gr${path}`));
      expect(response.status).toBe(301);
      expect(response.headers.get("x-middleware-request-x-nonce")).toBeNull();
    }
  });
});

const staticRenderingExport = /export\s+(?:const\s+(?:dynamic\s*=\s*["']force-static["']|revalidate\s*=\s*(?:[1-9]|false\b|Infinity\b)|fetchCache\s*=\s*["']force-cache["']|generateStaticParams\b)|(?:async\s+)?function\s+generateStaticParams\b)/;

it.each([
  'export const revalidate = 60;',
  'export const revalidate = false;',
  'export const revalidate = Infinity;',
  'export const dynamic = "force-static";',
  "export const dynamic = 'force-static';",
  'export const fetchCache = "force-cache";',
  'export function generateStaticParams() { return [{ id: "cached" }]; }',
  'export async function generateStaticParams() { return [{ id: "cached" }]; }',
  'export const generateStaticParams = async () => [{ id: "cached" }];',
])("the nonce guard rejects static rendering: %s", source => {
  expect(source).toMatch(staticRenderingExport);
});

it.each([
  'export const revalidate = 0;',
  'export const dynamic = "force-dynamic";',
  'export const fetchCache = "force-no-store";',
])("the nonce guard permits request rendering: %s", source => {
  expect(source).not.toMatch(staticRenderingExport);
});

it("every nonce-bearing page inherits request rendering with no child ISR/static override", () => {
  const app = fileURLToPath(new URL("./app", import.meta.url));
  const layout = readFileSync(resolve(app, "[locale]/layout.tsx"), "utf8");
  expect(layout).toContain('export const dynamic = "force-dynamic"');
  function children(dir: string): string[] {
    return readdirSync(dir, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? children(resolve(dir, entry.name)) : entry.name.endsWith(".tsx") && !entry.name.includes(".test.") ? [resolve(dir, entry.name)] : []);
  }
  const routes = children(app);
  expect(routes.filter(path => path.endsWith("page.tsx")).length).toBeGreaterThanOrEqual(9);
  for (const path of routes) {
    expect(readFileSync(path, "utf8"), path).not.toMatch(staticRenderingExport);
  }
});
