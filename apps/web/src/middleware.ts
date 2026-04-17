import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";
import { NextRequest, NextResponse } from "next/server";

const intlMiddleware = createMiddleware(routing);

export default function middleware(request: NextRequest) {
  // Serve docs/index.html (static landing page) at /
  if (request.nextUrl.pathname === "/") {
    return NextResponse.rewrite(new URL("/index.html", request.url));
  }
  return intlMiddleware(request);
}

export const config = {
  // Match all paths except static files (.*\\..*), api, _next, _vercel
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
