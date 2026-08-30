"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale } from "next-intl";
import Image from "next/image";
import { QRCodeSVG } from "qrcode.react";
import { signPayload } from "@/lib/crypto";

type State = "checking" | "nokey" | "verifying" | "success" | "error";
type QrState = "idle" | "loading" | "ready" | "authenticated" | "expired" | "error";

const LOCALSTORAGE_KEY = "ekklesia_private_key";
const LOCALSTORAGE_PUBKEY = "ekklesia_public_key";
const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.ekklesia.gr";
const QR_LIFETIME = 5 * 60 * 1000;
const subscribeHydration = () => () => {};
const clientSnapshot = () => true;
const serverSnapshot = () => false;

type QrData = { session_id: string; qr_data: string };
type LoginError = { code: "missing" | "identity" | "expired" | "connection" | "server"; detail?: string };
type InitialResult =
  | { kind: "qr"; data: QrData }
  | { kind: "redirect"; url: string }
  | { kind: "error"; error: LoginError; qr: boolean };

function initialSession(ready: boolean, nonce: string | null, returnUrl: string | null): {
  state: State; error: LoginError | null; publicKey: string | null;
} {
  if (!ready) return { state: "checking", error: null, publicKey: null };
  if (!nonce || !returnUrl) return { state: "error", error: { code: "missing" }, publicKey: null };
  try {
    const publicKey = localStorage.getItem(LOCALSTORAGE_PUBKEY);
    const hasPrivateKey = Boolean(localStorage.getItem(LOCALSTORAGE_KEY));
    return { state: publicKey && hasPrivateKey ? "verifying" : "nokey", error: null, publicKey };
  } catch {
    // Browser storage restrictions must not prevent signing in with the mobile app.
    return { state: "nokey", error: null, publicKey: null };
  }
}

async function startSession(nonce: string, publicKey: string | null): Promise<InitialResult> {
  let qr = true;
  try {
    let privateKey: string | null = null;
    try {
      if (publicKey && localStorage.getItem(LOCALSTORAGE_PUBKEY) === publicKey) {
        privateKey = localStorage.getItem(LOCALSTORAGE_KEY);
      }
    } catch {}
    if (publicKey && privateKey) {
      qr = false;
      const signatureHex = signPayload(privateKey, `discourse_sso:${nonce}:${publicKey}`);
      const res = await fetch(`${API_URL}/api/v1/sso/discourse/callback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nonce, public_key_hex: publicKey, signature_hex: signatureHex }),
      });
      if (res.status === 404) return { kind: "error", error: { code: "identity" }, qr };
      if (res.status === 410) return { kind: "error", error: { code: "expired" }, qr };
      const text = await res.text();
      let data;
      try { data = JSON.parse(text); } catch {}
      if (res.ok && typeof data?.redirect_url === "string" && data.redirect_url) {
        return { kind: "redirect", url: data.redirect_url };
      }
      return { kind: "error", error: { code: "server", detail: typeof data?.detail === "string" ? data.detail : `Error ${res.status}` }, qr };
    }
    const res = await fetch(`${API_URL}/api/v1/polis/qr-session?purpose=forum_login`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (typeof data?.session_id !== "string" || !data.session_id ||
        typeof data?.qr_data !== "string" || !data.qr_data) throw new Error("Invalid QR session");
    return { kind: "qr", data: { session_id: data.session_id, qr_data: data.qr_data } };
  } catch (err) {
    return { kind: "error", error: { code: "connection", detail: err instanceof Error ? err.message : "unknown" }, qr };
  }
}

function errorMessage(error: LoginError | null, isEl: boolean): string {
  switch (error?.code) {
    case "missing": return isEl ? "Μη έγκυρος σύνδεσμος — λείπουν παράμετροι." : "Invalid link — missing parameters.";
    case "identity": return isEl ? "Η ταυτότητα δεν βρέθηκε. Ολοκληρώστε πρώτα την εγγραφή." : "Identity not found. Please register first.";
    case "expired": return isEl ? "Η σύνδεση έληξε. Επιστρέψτε στο forum και δοκιμάστε ξανά." : "Session expired. Go back to the forum and try again.";
    case "connection": return `${isEl ? "Αδυναμία σύνδεσης" : "Connection failed"}: ${error.detail}`;
    default: return error?.detail || "";
  }
}

export default function SSOVerifyPage() {
  const locale = useLocale();
  const searchParams = useSearchParams();
  const nonce = searchParams.get("nonce");
  const returnUrl = searchParams.get("return_url");
  const ready = useSyncExternalStore(subscribeHydration, clientSnapshot, serverSnapshot);
  const [attempt, setAttempt] = useState(0);

  // A changed challenge or retry owns fresh state; SSR never reads browser keys.
  return <SSOSession key={JSON.stringify([nonce, returnUrl, ready, attempt])}
    nonce={nonce} returnUrl={returnUrl} ready={ready} isEl={locale === "el"}
    onRetry={() => setAttempt((value) => value + 1)} />;
}

function SSOSession({ nonce, returnUrl, ready, isEl, onRetry }: {
  nonce: string | null; returnUrl: string | null; ready: boolean; isEl: boolean; onRetry: () => void;
}) {
  const [initial] = useState(() => initialSession(ready, nonce, returnUrl));
  const [state, setState] = useState<State>(initial.state);
  const [error, setError] = useState<LoginError | null>(initial.error);
  const errorMsg = errorMessage(error, isEl);
  const [qrState, setQrState] = useState<QrState>(initial.state === "nokey" ? "loading" : "idle");
  const [qrData, setQrData] = useState<QrData | null>(null);
  const [qrError, setQrError] = useState("");
  const request = useRef<Promise<InitialResult> | null>(null);

  useEffect(() => {
    if (!ready || !nonce || !returnUrl || initial.error) return;
    let active = true;
    let finished = false;
    let pollBusy = false;
    let pollInterval: number | undefined;
    let expireTimeout: number | undefined;
    let redirectTimeout: number | undefined;

    function stopPolling() {
      window.clearInterval(pollInterval);
      window.clearTimeout(expireTimeout);
    }

    function redirect(url: string) {
      if (!active) return;
      setState("success");
      redirectTimeout = window.setTimeout(() => {
        if (active) window.location.href = url;
      }, 800);
    }

    async function completeForumQrLogin(sessionId: string) {
      try {
        const res = await fetch(`${API_URL}/api/v1/sso/discourse/qr-complete`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nonce, session_id: sessionId }),
        });
        if (!res.ok) throw new Error((await res.text()) || `HTTP ${res.status}`);
        const data = await res.json();
        if (typeof data.redirect_url !== "string" || !data.redirect_url) throw new Error("Missing redirect_url");
        redirect(data.redirect_url);
      } catch (err) {
        if (!active) return;
        setQrError(err instanceof Error ? err.message : "connection error");
        setQrState("error");
      }
    }

    function startPolling(data: QrData) {
      const deadline = Date.now() + QR_LIFETIME;
      function expire() {
        if (!active || finished) return;
        finished = true;
        stopPolling();
        setQrState("expired");
      }
      pollInterval = window.setInterval(async () => {
        if (!active || finished || pollBusy) return;
        if (Date.now() >= deadline) { expire(); return; }
        pollBusy = true;
        try {
          const res = await fetch(`${API_URL}/api/v1/polis/qr-session/${data.session_id}`);
          if (!res.ok) return;
          const status = await res.json();
          if (!active || finished) return;
          if (Date.now() >= deadline) { expire(); return; }
          if (status.status === "authenticated") {
            finished = true;
            stopPolling();
            setQrState("authenticated");
            await completeForumQrLogin(data.session_id);
          } else if (status.status === "expired") {
            expire();
          }
        } catch {} finally { pollBusy = false; }
      }, 2500);
      expireTimeout = window.setTimeout(expire, QR_LIFETIME);
    }

    // Reuse the parsed result across StrictMode replay; never replay a nonce-consuming POST.
    request.current ??= startSession(nonce, initial.publicKey);
    void request.current.then((result) => {
      if (!active) return;
      if (result.kind === "redirect") redirect(result.url);
      else if (result.kind === "qr") {
        setState("nokey");
        setQrData(result.data);
        setQrState("ready");
        startPolling(result.data);
      } else if (result.qr) {
        setState("nokey");
        setQrError(result.error.detail || "connection error");
        setQrState("error");
      } else {
        setError(result.error);
        setState("error");
      }
    });
    return () => {
      active = false;
      stopPolling();
      window.clearTimeout(redirectTimeout);
    };
  }, [ready, nonce, returnUrl, initial]);

  return (
    <>
    {/* Hide NavHeader on this page */}
    <style dangerouslySetInnerHTML={{ __html: "header { display: none !important; }" }} />
    <main className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-lg max-w-md w-full mx-6 p-10 text-center">
        {/* Back button */}
        <a href="https://pnyx.ekklesia.gr" className="inline-flex items-center gap-1 text-sm text-gray-400 hover:text-blue-600 mb-6 transition-colors">
          ← {isEl ? "Πίσω στο Forum" : "Back to Forum"}
        </a>

        {/* Logo */}
        <Image src="/pnx.png" alt="ekklesia" width={64} height={64} className="w-16 h-16 mx-auto mb-4" />
        <h1 className="text-xl font-black text-gray-900 mb-1">
          {isEl ? "Σύνδεση στο Forum" : "Forum Login"}
        </h1>
        <p className="text-sm text-gray-400 mb-8">pnyx.ekklesia.gr</p>

        {/* Checking */}
        {state === "checking" && (
          <div className="animate-pulse text-gray-400 text-sm">
            {isEl ? "Έλεγχος..." : "Checking..."}
          </div>
        )}

        {/* No Key */}
        {state === "nokey" && (
          <div>
            <div className="bg-gray-50 rounded-xl p-8 mb-6">
              {qrState === "loading" && (
                <div className="w-32 h-32 mx-auto mb-4 bg-white rounded-lg flex items-center justify-center text-sm text-gray-400">
                  {isEl ? "Φόρτωση..." : "Loading..."}
                </div>
              )}
              {qrState === "ready" && qrData && (
                <div className="w-40 h-40 mx-auto mb-4 bg-white rounded-lg p-3 shadow-sm flex items-center justify-center">
                  <QRCodeSVG value={qrData.qr_data} size={136} level="M" includeMargin={false} />
                </div>
              )}
              {qrState === "authenticated" && (
                <div className="w-32 h-32 mx-auto mb-4 bg-white rounded-lg flex items-center justify-center text-5xl">
                  ✅
                </div>
              )}
              {(qrState === "expired" || qrState === "error") && (
                <div className="w-32 h-32 mx-auto mb-4 bg-white rounded-lg border-2 border-dashed border-gray-300 flex items-center justify-center text-5xl">
                  {qrState === "expired" ? "⏰" : "❌"}
                </div>
              )}
              <p className="text-sm text-gray-500 leading-relaxed">
                {isEl
                  ? <>Σκανάρετε τον κωδικό QR με την εφαρμογή <strong>ekklesia</strong> για να συνδεθείτε.</>
                  : <>Scan the QR code with the <strong>ekklesia</strong> app to login.</>}
              </p>
              {qrState === "ready" && qrData && (
                <a
                  href={qrData.qr_data}
                  className="mt-4 flex min-h-12 w-full flex-col items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-white transition-colors hover:bg-blue-700"
                  aria-label={isEl
                    ? "Άνοιγμα στην εγκατεστημένη εφαρμογή ekklesia"
                    : "Open in the installed ekklesia app"}
                >
                  <span className="text-sm font-semibold">
                    {isEl ? "Άνοιγμα στην εφαρμογή ekklesia" : "Open in the ekklesia app"}
                  </span>
                  <span className="mt-0.5 text-[11px] text-blue-100">
                    {isEl ? "Μετά την επιβεβαίωση, επιστρέψτε εδώ" : "Return here after confirmation"}
                  </span>
                </a>
              )}
              {qrState === "expired" && (
                <button
                  onClick={onRetry}
                  className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold"
                >
                  {isEl ? "Νέος κωδικός QR" : "New QR code"}
                </button>
              )}
              {qrState === "error" && (
                <div className="mt-4 text-xs text-red-600 break-words">
                  {qrError || (isEl ? "Σφάλμα QR σύνδεσης" : "QR login error")}
                  <button
                    onClick={onRetry}
                    className="block mx-auto mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold"
                  >
                    {isEl ? "Δοκιμάστε ξανά" : "Try again"}
                  </button>
                </div>
              )}
            </div>
            <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-left">
              <p className="text-xs leading-relaxed text-blue-900">
                {isEl
                  ? "Για να συνδεθείτε χρειάζεστε επαληθευμένη ταυτότητα στην εφαρμογή ekklesia. Εγκαταστήστε την εφαρμογή, ολοκληρώστε την επαλήθευση και σαρώστε τον παραπάνω κωδικό QR."
                  : "Forum login requires a verified identity in the ekklesia app. Install the app, complete verification, and scan the QR code above."}
              </p>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2">
              <a
                href="https://play.google.com/apps/testing/ekklesia.gr"
                target="_blank"
                rel="noopener noreferrer"
                className="flex min-h-16 min-w-0 flex-col justify-center rounded-lg border border-gray-200 bg-white px-3 py-3 text-center text-gray-800 transition-colors hover:border-blue-400 hover:text-blue-700"
              >
                <span className="block text-sm font-semibold">Google Play</span>
                <span className="mt-1 block text-[11px] text-gray-500">
                  {isEl ? "Κλειστή δοκιμή" : "Closed testing"}
                </span>
              </a>
              <a
                href="https://f-droid.org/packages/ekklesia.gr/"
                target="_blank"
                rel="noopener noreferrer"
                className="flex min-h-16 min-w-0 flex-col justify-center rounded-lg border border-gray-200 bg-white px-3 py-3 text-center text-gray-800 transition-colors hover:border-blue-400 hover:text-blue-700"
              >
                <span className="block text-sm font-semibold">F-Droid</span>
                <span className="mt-1 block text-[11px] text-gray-500">
                  {isEl ? "Διαθέσιμο" : "Available"}
                </span>
              </a>
              <a
                href="https://github.com/NeaBouli/pnyx/releases/download/v1.0.29/ekklesia-v1.0.29-vC58-DIRECT.apk"
                target="_blank"
                rel="noopener noreferrer"
                className="flex min-h-16 min-w-0 flex-col justify-center rounded-lg border border-gray-200 bg-white px-3 py-3 text-center text-gray-800 transition-colors hover:border-blue-400 hover:text-blue-700"
              >
                <span className="block text-sm font-semibold">APK</span>
                <span className="mt-1 block text-[11px] text-gray-500">
                  {isEl ? "Άμεση λήψη" : "Direct download"}
                </span>
              </a>
              <button
                type="button"
                disabled
                aria-label={isEl ? "iOS — Σύντομα" : "iOS — Coming soon"}
                className="flex min-h-16 min-w-0 cursor-not-allowed flex-col justify-center rounded-lg border border-gray-200 bg-gray-50 px-3 py-3 text-center text-gray-400"
              >
                <span className="block text-sm font-semibold">iOS</span>
                <span className="mt-1 block text-[11px]">
                  {isEl ? "Σύντομα" : "Coming soon"}
                </span>
              </button>
            </div>
          </div>
        )}

        {/* Verifying */}
        {state === "verifying" && (
          <div>
            <div className="w-12 h-12 border-4 border-gray-200 border-t-blue-600 rounded-full mx-auto mb-5 animate-spin" />
            <p className="text-gray-600 font-medium">
              {isEl ? "Επαλήθευση ταυτότητας..." : "Verifying identity..."}
            </p>
            <p className="text-sm text-gray-400 mt-1">
              {isEl ? "Παρακαλώ περιμένετε" : "Please wait"}
            </p>
          </div>
        )}

        {/* Success */}
        {state === "success" && (
          <div>
            <div className="w-12 h-12 mx-auto mb-4 text-green-500">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="8 12 11 15 16 9"/>
              </svg>
            </div>
            <p className="text-green-600 font-semibold">
              {isEl ? "Επιτυχής σύνδεση — ανακατεύθυνση..." : "Login successful — redirecting..."}
            </p>
          </div>
        )}

        {/* Error */}
        {state === "error" && (
          <div>
            <div className="w-12 h-12 mx-auto mb-4 text-red-500">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
            </div>
            <div className="bg-red-50 rounded-lg p-3 mb-5 text-red-700 text-sm break-words">
              {errorMsg}
            </div>
            <button
              onClick={onRetry}
              className="px-6 py-2.5 bg-gray-100 text-gray-600 border border-gray-200 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
            >
              {isEl ? "Δοκιμάστε ξανά" : "Try again"}
            </button>
          </div>
        )}

        {/* Footer */}
        <div className="mt-8 text-xs text-gray-400">
          <a href="https://ekklesia.gr" className="text-blue-600 hover:text-blue-700">ekklesia.gr</a>
          {" — "}
          {isEl ? "Ψηφιακή Δημοκρατία" : "Digital Democracy"}
        </div>
      </div>
    </main>
    </>
  );
}
