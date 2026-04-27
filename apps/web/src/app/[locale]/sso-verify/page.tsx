"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale } from "next-intl";
import Link from "next/link";

type State = "checking" | "nokey" | "verifying" | "success" | "error";

const LOCALSTORAGE_KEY = "ekklesia_private_key";
const LOCALSTORAGE_PUBKEY = "ekklesia_public_key";

export default function SSOVerifyPage() {
  const locale = useLocale();
  const searchParams = useSearchParams();
  const nonce = searchParams.get("nonce");
  const returnUrl = searchParams.get("return_url");

  const [state, setState] = useState<State>("checking");
  const [errorMsg, setErrorMsg] = useState("");

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
      return;
    }

    authenticate(pubKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce, returnUrl]);

  async function authenticate(pubKeyHex: string) {
    setState("verifying");
    try {
      const res = await fetch(`${API_URL}/api/v1/sso/discourse/callback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nonce, public_key_hex: pubKeyHex }),
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
    <main className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-lg max-w-md w-full mx-6 p-10 text-center">
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
              <div className="w-32 h-32 mx-auto mb-4 bg-white rounded-lg border-2 border-dashed border-gray-300 flex items-center justify-center">
                <svg className="w-20 h-20 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="3" y="3" width="7" height="7" rx="1"/>
                  <rect x="14" y="3" width="7" height="7" rx="1"/>
                  <rect x="3" y="14" width="7" height="7" rx="1"/>
                  <rect x="14" y="14" width="3" height="3"/>
                  <rect x="18" y="18" width="3" height="3"/>
                </svg>
              </div>
              <p className="text-sm text-gray-500 leading-relaxed">
                {isEl
                  ? <>Σκανάρετε τον κωδικό QR με την εφαρμογή <strong>ekklesia</strong> για να συνδεθείτε.</>
                  : <>Scan the QR code with the <strong>ekklesia</strong> app to login.</>}
              </p>
            </div>
            <Link
              href={`/${locale}/verify`}
              className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl font-semibold text-sm hover:bg-blue-700 transition-colors"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="5" y="2" width="14" height="20" rx="2"/>
                <line x1="12" y1="18" x2="12" y2="18" strokeLinecap="round" strokeWidth="3"/>
              </svg>
              {isEl ? "Εγγραφή μέσω ekklesia" : "Register via ekklesia"}
            </Link>
            <p className="text-xs text-gray-400 mt-4">
              {isEl
                ? "Χρειάζεστε επαληθευμένο λογαριασμό ekklesia.gr"
                : "You need a verified ekklesia.gr account"}
            </p>
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
  );
}
