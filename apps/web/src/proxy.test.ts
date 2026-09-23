import { describe, it, expect, vi } from "vitest";

// Mock next-intl middleware and routing before importing proxy
vi.mock("next-intl/middleware", () => ({
  default: () => () => new Response(null, { status: 200 }),
}));
vi.mock("./i18n/routing", () => ({ routing: {} }));

import { NextRequest } from "next/server";
import proxy from "./proxy";

const CANONICAL_APK =
  "https://github.com/NeaBouli/pnyx/releases/download/v1.0.32/ekklesia-v1.0.32-vC61-DIRECT.apk";

describe("proxy – legacy download redirects (T-350)", () => {
  const legacyPaths = ["/download", "/download/", "/el/download", "/en/download"];

  for (const path of legacyPaths) {
    it(`redirects ${path} → canonical GitHub release asset with 302`, () => {
      const req = new NextRequest(new URL(path, "https://ekklesia.gr"));
      const res = proxy(req);
      expect(res.status).toBe(302);
      expect(res.headers.get("location")).toBe(CANONICAL_APK);
    });
  }

  it("never redirects to the broken /download/ekklesia-latest.apk path", () => {
    for (const path of legacyPaths) {
      const req = new NextRequest(new URL(path, "https://ekklesia.gr"));
      const res = proxy(req);
      expect(res.headers.get("location")).not.toContain("ekklesia-latest.apk");
    }
  });

  it("does not interfere with the root rewrite", () => {
    const req = new NextRequest(new URL("/", "https://ekklesia.gr"));
    const res = proxy(req);
    // Root should rewrite (not redirect) to /index.html
    expect(res.status).not.toBe(302);
  });
});

describe("next.config.mjs – legacy APK redirect (T-350)", () => {
  it("redirects /download/ekklesia-latest.apk → canonical GitHub release asset", async () => {
    // The middleware matcher excludes dotted paths, so this redirect is
    // configured in next.config.mjs.  Import and verify the config entry.
    // @ts-expect-error -- .mjs has no type declarations
    const mod = await import("../../next.config.mjs");
    const config = mod.default;
    // withPWA(withNextIntl(nextConfig)) wraps the config; the redirects()
    // function is passed through by the wrappers.
    const redirects = await config.redirects();
    const apkRedirect = redirects.find(
      (r: { source: string }) => r.source === "/download/ekklesia-latest.apk",
    );
    expect(apkRedirect).toBeDefined();
    expect(apkRedirect.destination).toBe(CANONICAL_APK);
    expect(apkRedirect.permanent).toBe(false);
  });
});
