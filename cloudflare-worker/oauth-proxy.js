// POLIS OAuth Proxy — Cloudflare Worker
// Exchanges GitHub OAuth code for access token.
// This is the ONLY server-side component.
//
// Deploy:
//   wrangler deploy
// Set secret:
//   wrangler secret put GITHUB_CLIENT_SECRET
//   wrangler secret put GITHUB_CLIENT_ID

const ALLOWED_ORIGINS = [
  "https://neabouli.github.io",
  "https://ekklesia.gr",
  "http://localhost:8080",
];

function corsHeaders(origin) {
  const allowed = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const cors = corsHeaders(origin);

    // Preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    // Health check
    if (request.method === "GET") {
      return new Response(
        JSON.stringify({ status: "ok", service: "polis-oauth-proxy" }),
        { status: 200, headers: { ...cors, "Content-Type": "application/json" } }
      );
    }

    // Token exchange
    if (request.method === "POST") {
      try {
        const { code, redirect_uri } = await request.json();

        if (!code) {
          return new Response(
            JSON.stringify({ error: "missing_code" }),
            { status: 400, headers: { ...cors, "Content-Type": "application/json" } }
          );
        }

        const tokenRes = await fetch("https://github.com/login/oauth/access_token", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
          },
          body: JSON.stringify({
            client_id: env.GITHUB_CLIENT_ID,
            client_secret: env.GITHUB_CLIENT_SECRET,
            code: code,
            redirect_uri: redirect_uri || undefined,
          }),
        });

        const data = await tokenRes.json();

        if (data.error) {
          return new Response(
            JSON.stringify({ error: data.error, description: data.error_description }),
            { status: 400, headers: { ...cors, "Content-Type": "application/json" } }
          );
        }

        // Return only the access token — never expose other fields
        return new Response(
          JSON.stringify({ access_token: data.access_token }),
          { status: 200, headers: { ...cors, "Content-Type": "application/json" } }
        );

      } catch (err) {
        return new Response(
          JSON.stringify({ error: "internal_error", message: err.message }),
          { status: 500, headers: { ...cors, "Content-Type": "application/json" } }
        );
      }
    }

    return new Response("Method not allowed", { status: 405, headers: cors });
  },
};
