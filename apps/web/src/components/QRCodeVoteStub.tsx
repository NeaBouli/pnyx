"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { QRCodeSVG } from "qrcode.react";
import { useLocale } from "next-intl";

const API_BASE = "https://api.ekklesia.gr";
const POLL_INTERVAL_MS = 2500;
const SESSION_TTL_MS = 5 * 60 * 1000; // 5 minutes

type SessionStatus = "loading" | "ready" | "authenticated" | "expired" | "error";

interface QRSession {
  session_id: string;
  challenge: string;
  qr_data: string;
}

interface Props {
  billId?: string;
  purpose?: "vote" | "consensus" | "ticket" | "forum_login";
  onAuthenticated?: (sessionId: string) => void;
}

export default function QRCodeVoteStub({ billId, purpose = "ticket", onAuthenticated }: Props) {
  const locale = useLocale();
  const isEl = locale === "el";
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [session, setSession] = useState<QRSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionAttempt, setSessionAttempt] = useState(0);

  // Bei geändertem billId/purpose sofort in den Ladezustand zurücksetzen
  const sessionKey = `${billId ?? ""}:${purpose}`;
  const [prevSessionKey, setPrevSessionKey] = useState(sessionKey);
  if (prevSessionKey !== sessionKey) {
    setPrevSessionKey(sessionKey);
    setStatus("loading");
    setSession(null);
    setError(null);
  }

  // Immer die neueste Callback-Referenz pollen, ohne den Poll-Effekt neu zu starten
  const onAuthenticatedRef = useRef(onAuthenticated);
  useEffect(() => {
    onAuthenticatedRef.current = onAuthenticated;
  }, [onAuthenticated]);

  // Reines Laden der Session ohne State-Zugriff
  const fetchSession = useCallback(async (): Promise<QRSession> => {
    const params = new URLSearchParams({ purpose });
    if (billId) params.set("bill_id", billId);
    const res = await fetch(`${API_BASE}/api/v1/polis/qr-session?${params}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }, [billId, purpose]);

  const createSession = useCallback(() => {
    setStatus("loading");
    setSession(null);
    setError(null);
    setSessionAttempt((a) => a + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchSession().then(
      (data) => {
        if (cancelled) return;
        setSession(data);
        setStatus("ready");
      },
      (e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error && e.message ? e.message : "Connection error");
        setStatus("error");
      }
    );
    return () => {
      cancelled = true;
    };
  }, [fetchSession, sessionAttempt]);

  // Poll for authentication status
  useEffect(() => {
    if (status !== "ready" || !session) return;

    let active = true;

    const pollInterval = setInterval(async () => {
      if (!active) return;
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/polis/qr-session/${session.session_id}`
        );
        if (!res.ok) return;
        const data = await res.json();
        if (!active) return;
        if (data.status === "authenticated") {
          active = false;
          setStatus("authenticated");
          clearInterval(pollInterval);
          onAuthenticatedRef.current?.(session.session_id);
        } else if (data.status === "expired") {
          active = false;
          setStatus("expired");
          clearInterval(pollInterval);
        }
      } catch {}
    }, POLL_INTERVAL_MS);

    const expireTimeout = setTimeout(() => {
      if (!active) return;
      active = false;
      setStatus("expired");
      clearInterval(pollInterval);
    }, SESSION_TTL_MS);

    return () => {
      active = false;
      clearInterval(pollInterval);
      clearTimeout(expireTimeout);
    };
  }, [status, session]);

  return (
    <div style={{
      background: "#f0f6ff",
      border: "1.5px solid #2563eb22",
      borderRadius: 16,
      padding: "clamp(16px, 6vw, 32px) clamp(12px, 4vw, 24px)",
      textAlign: "center",
      marginTop: 24,
      maxWidth: "100%",
      overflow: "hidden",
    }}>
      <h3 style={{ color: "#2563eb", fontWeight: 800, fontSize: 18, marginBottom: 8 }}>
        {isEl ? "Ψηφίστε μέσω QR Code" : "Vote via QR Code"}
      </h3>

      {/* LOADING */}
      {status === "loading" && (
        <div style={{ padding: 32, color: "#6b7280", fontSize: 14 }}>
          {isEl ? "Φόρτωση κωδικού QR..." : "Loading QR code..."}
        </div>
      )}

      {/* READY — QR Code visible */}
      {status === "ready" && session && (
        <>
          <p style={{ color: "#374151", fontSize: 14, marginBottom: 20 }}>
            {isEl
              ? "Σκανάρετε με την εφαρμογή ekklesia για να ψηφίσετε απευθείας από τον browser."
              : "Scan with the ekklesia app to vote directly from your browser."}
          </p>
          <div style={{
            display: "inline-block",
            background: "white",
            padding: 16,
            borderRadius: 12,
            boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
            marginBottom: 16,
            width: "min(232px, 100%)",
            maxWidth: "100%",
            boxSizing: "border-box",
          }}>
            <QRCodeSVG
              value={session.qr_data}
              size={200}
              level="M"
              includeMargin={false}
              style={{ display: "block", width: "100%", height: "auto" }}
            />
          </div>
          <p style={{ color: "#9ca3af", fontSize: 12, marginBottom: 16 }}>
            {isEl ? "Ο κωδικός λήγει σε 5 λεπτά" : "Code expires in 5 minutes"}
          </p>
          <a
            href="https://ekklesia.gr/#download"
            style={{
              display: "inline-block",
              background: "#2563eb",
              color: "white",
              borderRadius: 8,
              padding: "10px 20px",
              fontSize: 14,
              fontWeight: 700,
              textDecoration: "none",
            }}
          >
            {isEl ? "Κατεβάστε την εφαρμογή" : "Download the app"}
          </a>
        </>
      )}

      {/* AUTHENTICATED */}
      {status === "authenticated" && (
        <div style={{ padding: 24 }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
          <p style={{ color: "#16a34a", fontWeight: 700, fontSize: 18 }}>
            {isEl ? "Επιτυχής σύνδεση!" : "Successfully authenticated!"}
          </p>
          <p style={{ color: "#6b7280", fontSize: 14, marginTop: 8 }}>
            {isEl
              ? "Ψηφίστε παραπάνω — τα κουμπιά είναι τώρα ενεργά."
              : "Vote above — the buttons are now active."}
          </p>
        </div>
      )}

      {/* EXPIRED */}
      {status === "expired" && (
        <div style={{ padding: 24 }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>⏰</div>
          <p style={{ color: "#d97706", fontWeight: 700, fontSize: 16, marginBottom: 16 }}>
            {isEl ? "Ο κωδικός έληξε" : "Code expired"}
          </p>
          <button
            onClick={createSession}
            style={{
              background: "#2563eb",
              color: "white",
              border: "none",
              borderRadius: 8,
              padding: "10px 24px",
              fontSize: 14,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            {isEl ? "Δημιουργία νέου κωδικού" : "Generate new code"}
          </button>
        </div>
      )}

      {/* ERROR */}
      {status === "error" && (
        <div style={{ padding: 24 }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>❌</div>
          <p style={{ color: "#dc2626", fontSize: 14, marginBottom: 16 }}>
            {error}
          </p>
          <button
            onClick={createSession}
            style={{
              background: "#2563eb",
              color: "white",
              border: "none",
              borderRadius: 8,
              padding: "10px 24px",
              fontSize: 14,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            {isEl ? "Προσπαθήστε ξανά" : "Try again"}
          </button>
        </div>
      )}
    </div>
  );
}
