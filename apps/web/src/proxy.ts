import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";
import { NextRequest, NextResponse } from "next/server";
import { createNonce, noncePolicy } from "./lib/csp";

const intlMiddleware = createMiddleware(routing);

// Wiki pages that exist as static HTML in docs/wiki/
const WIKI_PAGES = new Set([
  "index", "faq", "api", "architecture", "contributing",
  "database", "modules", "privacy", "roadmap", "security", "whitepaper",
]);

export default function proxy(request: NextRequest) {
  const p = request.nextUrl.pathname;

  // Old Direct-channel Android clients and Samsung Internet may still open the
  // historical download page route. Redirect to the canonical GitHub release
  // asset. The legacy /download/ekklesia-latest.apk path is handled by
  // next.config.mjs redirects (middleware matcher excludes dotted paths).
  if (p === "/download" || p === "/download/" || p === "/el/download" || p === "/en/download") {
    return NextResponse.redirect(
      "https://github.com/NeaBouli/pnyx/releases/download/v1.0.37/ekklesia-v1.0.37-vC66-DIRECT.apk",
      302,
    );
  }

  // Serve docs/index.html (static landing page) at /
  if (p === "/") {
    return NextResponse.rewrite(new URL("/index.html", request.url));
  }

  // Canonical static POLIS ticket board. Keep sitemap/canonical on the final
  // index file to avoid the old /tickets -> /el/tickets -> /tickets/index.html chain.
  if (p === "/tickets" || p === "/tickets/") {
    return NextResponse.redirect(new URL("/tickets/index.html", request.url), 301);
  }

  // Redirect /{el|en}/wiki, /{el|en}/wiki/*, /{el|en}/community,
  // /{el|en}/tickets, /{el|en}/votes to their static docs/ equivalents
  const localeStatic = p.match(/^\/(el|en)\/(wiki|community|tickets|votes)(\/(.*))?$/);
  if (localeStatic) {
    const section = localeStatic[2];
    const sub = localeStatic[4] || "";

    if (section === "community") {
      return NextResponse.redirect(new URL("/community.html", request.url), 301);
    }
    if (section === "tickets") {
      return NextResponse.redirect(new URL(`/tickets/${sub || "index.html"}`, request.url), 301);
    }
    if (section === "votes") {
      return NextResponse.redirect(new URL("/el/bills", request.url), 301);
    }
    // section === "wiki"
    if (!sub || sub === "index") {
      return NextResponse.redirect(new URL("/wiki/index.html", request.url), 301);
    }
    if (WIKI_PAGES.has(sub)) {
      return NextResponse.redirect(new URL(`/wiki/${sub}.html`, request.url), 301);
    }
    // Unknown wiki subpage — redirect to wiki index
    return NextResponse.redirect(new URL("/wiki/index.html", request.url), 301);
  }

  // Next 16 reads CSP from the forwarded request to nonce bootstrap, Flight,
  // streaming metadata and framework scripts. Never trust a client nonce/CSP.
  const nonce = createNonce();
  const policy = noncePolicy(nonce);
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", policy);
  headers.delete("Content-Security-Policy-Report-Only");
  const response = intlMiddleware(new NextRequest(request, { headers }));
  response.headers.delete("Content-Security-Policy-Report-Only");
  // Next's router copies middleware response headers over request overrides.
  // In rollback mode next.config supplies legacy enforcement without replacing
  // the nonce-bearing request CSP used by the renderer.
  if (process.env.CSP_ENFORCE !== "false") {
    response.headers.set("Content-Security-Policy", policy);
  }
  // Nonce-bearing HTML/RSC must never be replayed with a new response header.
  response.headers.set("Cache-Control", "private, no-store, max-age=0");
  return response;
}

export const config = {
  // Static assets bypass the proxy; public bill identifiers may contain dots.
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)", "/(el|en)/bills/:path*"],
};
