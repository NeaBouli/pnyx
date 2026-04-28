"use client";

import { useEffect, useState, useCallback } from "react";
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
  purpose?: "vote" | "ticket" | "forum_login";
}

export default function QRCodeVoteStub({ billId, purpose = "ticket" }: Props) {
  const locale = useLocale();
  const isEl = locale === "el";
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [session, setSession] = useState<QRSession | null>(null);
  const [error, setError] = useState<string | null>(null);

  const createSession = useCallback(async () => {
    setStatus("loading");
    setSession(null);
    setError(null);
    try {
      const params = new URLSearchParams({ purpose });
      if (billId) params.set("bill_id", billId);
      const res = await fetch(`${API_BASE}/api/v1/polis/qr-session?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSession(data);
      setStatus("ready");
    } catch (e: any) {
      setError(e.message || "Connection error");
      setStatus("error");
    }
  }, [billId, purpose]);

  useEffect(() => {
    createSession();
  }, [createSession]);

  // Poll for authentication status
  useEffect(() => {
    if (status !== "ready" || !session) return;

    const pollInterval = setInterval(async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/polis/qr-session/${session.session_id}`
        );
        if (!res.ok) return;
        const data = await res.json();

        if (data.status === "authenticated") {
          setStatus("authenticated");
          clearInterval(pollInterval);
        } else if (data.status === "expired") {
          setStatus("expired");
          clearInterval(pollInterval);
        }
      } catch {}
    }, POLL_INTERVAL_MS);

    const expireTimeout = setTimeout(() => {
      setStatus("expired");
      clearInterval(pollInterval);
    }, SESSION_TTL_MS);

    return () => {
      clearInterval(pollInterval);
      clearTimeout(expireTimeout);
    };
  }, [status, session]);

  return (
    <div style={{
      background: "#f0f6ff",
      border: "1.5px solid #2563eb22",
      borderRadius: 16,
      padding: "32px 24px",
      textAlign: "center",
      marginTop: 24,
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
          }}>
            <QRCodeSVG
              value={session.qr_data}
              size={200}
              level="M"
              includeMargin={false}
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
              ? "Μπορείτε τώρα να ψηφίσετε από τον browser."
              : "You can now vote from the browser."}
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
