import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";
import { NextRequest, NextResponse } from "next/server";

const intlMiddleware = createMiddleware(routing);

// Wiki pages that exist as static HTML in docs/wiki/
const WIKI_PAGES = new Set([
  "index", "faq", "api", "architecture", "contributing",
  "database", "modules", "privacy", "roadmap", "security", "whitepaper",
]);

export default function middleware(request: NextRequest) {
  const p = request.nextUrl.pathname;

  // Serve docs/index.html (static landing page) at /
  if (p === "/") {
    return NextResponse.rewrite(new URL("/index.html", request.url));
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

  return intlMiddleware(request);
}

export const config = {
  // Match all paths except static files (.*\\..*), api, _next, _vercel
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
