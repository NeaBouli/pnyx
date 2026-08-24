"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale } from "next-intl";
import { QRCodeSVG } from "qrcode.react";
import { signPayload } from "@/lib/crypto";

type State = "checking" | "nokey" | "verifying" | "success" | "error";
type QrState = "idle" | "loading" | "ready" | "authenticated" | "expired" | "error";

const LOCALSTORAGE_KEY = "ekklesia_private_key";
const LOCALSTORAGE_PUBKEY = "ekklesia_public_key";

export default function SSOVerifyPage() {
  const locale = useLocale();
  const searchParams = useSearchParams();
  const nonce = searchParams.get("nonce");
  const returnUrl = searchParams.get("return_url");

  const [state, setState] = useState<State>("checking");
  const [errorMsg, setErrorMsg] = useState("");
  const [qrState, setQrState] = useState<QrState>("idle");
  const [qrData, setQrData] = useState<{ session_id: string; qr_data: string } | null>(null);
  const [qrError, setQrError] = useState("");

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.ekklesia.gr";
  const isEl = locale === "el";

  useEffect(() => {
    if (!nonce || !returnUrl) {
      setErrorMsg(isEl
        ? "Μη έγκυρος σύνδεσμος — λείπουν παράμετροι."
        : "Invalid link — missing parameters.");
      setState("error");
      return;
    }

    const pubKey = localStorage.getItem(LOCALSTORAGE_PUBKEY);
    const privKey = localStorage.getItem(LOCALSTORAGE_KEY);

    if (!pubKey || !privKey) {
      setState("nokey");
      createForumQrSession();
      return;
    }

    authenticate(pubKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce, returnUrl]);

  useEffect(() => {
    if (state !== "nokey" || qrState !== "ready" || !qrData || !nonce) return;

    const pollInterval = window.setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/polis/qr-session/${qrData.session_id}`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "authenticated") {
          window.clearInterval(pollInterval);
          setQrState("authenticated");
          await completeForumQrLogin(qrData.session_id);
        } else if (data.status === "expired") {
          window.clearInterval(pollInterval);
          setQrState("expired");
        }
      } catch {}
    }, 2500);

    const expireTimeout = window.setTimeout(() => {
      setQrState("expired");
      window.clearInterval(pollInterval);
    }, 5 * 60 * 1000);

    return () => {
      window.clearInterval(pollInterval);
      window.clearTimeout(expireTimeout);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, qrState, qrData, nonce]);

  async function createForumQrSession() {
    setQrState("loading");
    setQrData(null);
    setQrError("");
    try {
      const res = await fetch(`${API_URL}/api/v1/polis/qr-session?purpose=forum_login`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setQrData({ session_id: data.session_id, qr_data: data.qr_data });
      setQrState("ready");
    } catch (err) {
      setQrError(err instanceof Error ? err.message : "connection error");
      setQrState("error");
    }
  }

  async function completeForumQrLogin(sessionId: string) {
    try {
      const res = await fetch(`${API_URL}/api/v1/sso/discourse/qr-complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nonce, session_id: sessionId }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.redirect_url) {
        setState("success");
        setTimeout(() => { window.location.href = data.redirect_url; }, 800);
        return;
      }
      throw new Error("Missing redirect_url");
    } catch (err) {
      setQrError(err instanceof Error ? err.message : "connection error");
      setQrState("error");
    }
  }

  async function authenticate(pubKeyHex: string) {
    setState("verifying");
    try {
      const privKey = localStorage.getItem(LOCALSTORAGE_KEY);
      if (!privKey) { setState("nokey"); return; }

      // Sign challenge to prove key possession
      const challenge = `discourse_sso:${nonce}:${pubKeyHex}`;
      const signatureHex = signPayload(privKey, challenge);

      const res = await fetch(`${API_URL}/api/v1/sso/discourse/callback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nonce, public_key_hex: pubKeyHex, signature_hex: signatureHex }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.redirect_url) {
          setState("success");
          setTimeout(() => { window.location.href = data.redirect_url; }, 800);
          return;
        }
      }

      if (res.status === 404) {
        setErrorMsg(isEl
          ? "Η ταυτότητα δεν βρέθηκε. Ολοκληρώστε πρώτα την εγγραφή."
          : "Identity not found. Please register first.");
        setState("error");
        return;
      }

      if (res.status === 410) {
        setErrorMsg(isEl
          ? "Η σύνδεση έληξε. Επιστρέψτε στο forum και δοκιμάστε ξανά."
          : "Session expired. Go back to the forum and try again.");
        setState("error");
        return;
      }

      const text = await res.text();
      let detail: string;
      try { detail = JSON.parse(text).detail; } catch { detail = text; }
      setErrorMsg(detail || `Error ${res.status}`);
      setState("error");
    } catch (err) {
      setErrorMsg(isEl
        ? `Αδυναμία σύνδεσης: ${err instanceof Error ? err.message : "unknown"}`
        : `Connection failed: ${err instanceof Error ? err.message : "unknown"}`);
      setState("error");
    }
  }

  function handleRetry() {
    const pk = localStorage.getItem(LOCALSTORAGE_PUBKEY);
    if (!pk) { setState("nokey"); return; }
    authenticate(pk);
  }

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
        <img src="/pnx.png" alt="ekklesia" className="w-16 h-16 mx-auto mb-4" />
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
              {qrState === "expired" && (
                <button
                  onClick={createForumQrSession}
                  className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold"
                >
                  {isEl ? "Νέος κωδικός QR" : "New QR code"}
                </button>
              )}
              {qrState === "error" && (
                <div className="mt-4 text-xs text-red-600 break-words">
                  {qrError || (isEl ? "Σφάλμα QR σύνδεσης" : "QR login error")}
                  <button
                    onClick={createForumQrSession}
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
              onClick={handleRetry}
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
