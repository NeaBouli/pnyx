"use client";

import { useState } from "react";
import { useLocale } from "next-intl";
import Link from "next/link";
import { ekklesia } from "@/lib/api";

type Phase = "form" | "success" | "already";

const REGIONS = [
  { value: "",                        label_el: "— Περιοχή (προαιρετικά) —", label_en: "— Region (optional) —" },
  { value: "REG_ATTICA",              label_el: "Αττική",                     label_en: "Attica" },
  { value: "REG_CENTRAL_MACEDONIA",   label_el: "Κεντρική Μακεδονία",        label_en: "Central Macedonia" },
  { value: "REG_CRETE",               label_el: "Κρήτη",                     label_en: "Crete" },
  { value: "REG_PELOPONNESE",         label_el: "Πελοπόννησος",              label_en: "Peloponnese" },
  { value: "REG_THESSALY",            label_el: "Θεσσαλία",                  label_en: "Thessaly" },
  { value: "REG_STEREA",              label_el: "Στερεά Ελλάδα",             label_en: "Central Greece" },
  { value: "REG_WEST_GREECE",         label_el: "Δυτική Ελλάδα",             label_en: "West Greece" },
  { value: "REG_EPIRUS",              label_el: "Ήπειρος",                   label_en: "Epirus" },
  { value: "REG_WEST_MACEDONIA",      label_el: "Δυτική Μακεδονία",          label_en: "West Macedonia" },
  { value: "REG_EAST_MACEDONIA",      label_el: "Ανατολική Μακεδονία",       label_en: "East Macedonia" },
  { value: "REG_IONIAN",              label_el: "Ιόνια Νησιά",              label_en: "Ionian Islands" },
  { value: "REG_NORTH_AEGEAN",        label_el: "Βόρειο Αιγαίο",            label_en: "North Aegean" },
  { value: "REG_SOUTH_AEGEAN",        label_el: "Νότιο Αιγαίο",             label_en: "South Aegean" },
];

export default function VerifyPage() {
  const locale = useLocale();
  const [phase, setPhase]           = useState<Phase>("form");
  const [phone, setPhone]           = useState("");
  const [region, setRegion]         = useState("");
  const [gender, setGender]         = useState("GENDER_NO_ANSWER");
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [privateKey, setPrivateKey] = useState<string | null>(null);
  const [nullifier, setNullifier]   = useState<string | null>(null);
  const [copied, setCopied]         = useState(false);

  // Check if already verified
  const existingKey = typeof window !== "undefined"
    ? localStorage.getItem("ekklesia_nullifier_hash")
    : null;

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await ekklesia.verify(phone, region || undefined, gender);
      const data = res.data;

      // Store in localStorage (Beta — Secure Enclave in Mobile V2)
      localStorage.setItem("ekklesia_nullifier_hash", data.nullifier_hash);
      localStorage.setItem("ekklesia_public_key", data.public_key_hex);

      setPrivateKey(data.private_key_hex);
      setNullifier(data.nullifier_hash);
      setPhase("success");
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status: number; data?: { detail?: string } } };
      if (axiosErr.response?.status === 409) {
        setPhase("already");
      } else if (axiosErr.response?.status === 400) {
        setError(axiosErr.response.data?.detail || "Ungültige Nummer.");
      } else {
        setError(locale === "el"
          ? "Σύνδεση με API αποτυχημένη. Λειτουργεί το backend;"
          : "API connection failed. Is the backend running?");
      }
    } finally {
      setLoading(false);
    }
  }

  async function copyKey() {
    if (privateKey) {
      await navigator.clipboard.writeText(privateKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  // ── ALREADY VERIFIED ─────────────────────────────────────────────────────
  if (phase === "already" || (existingKey && phase === "form")) {
    return (
      <main className="min-h-screen bg-gray-950 text-white">
        <div className="max-w-lg mx-auto px-6 py-20 text-center">
          <div className="text-5xl mb-6">✅</div>
          <h1 className="text-3xl font-bold mb-4">
            {locale === "el" ? "Ήδη Επαληθευμένοι" : "Already Verified"}
          </h1>
          <p className="text-gray-400 mb-8">
            {locale === "el"
              ? "Η ταυτότητά σας έχει ήδη επαληθευτεί. Μπορείτε να ψηφίσετε."
              : "Your identity is already verified. You can vote."}
          </p>
          {existingKey && (
            <div className="bg-gray-900 rounded-xl p-4 mb-6 border border-gray-800 text-left">
              <p className="text-xs text-gray-500 mb-1">Nullifier Hash</p>
              <p className="text-xs font-mono text-gray-400 break-all">{existingKey}</p>
            </div>
          )}
          <Link
            href={`/${locale}/bills`}
            className="inline-block px-8 py-3 bg-blue-600 hover:bg-blue-500 rounded-xl font-semibold transition-colors"
          >
            🏛️ {locale === "el" ? "Ψηφίστε τώρα" : "Vote now"} →
          </Link>
        </div>
      </main>
    );
  }

  // ── SUCCESS ───────────────────────────────────────────────────────────────
  if (phase === "success") {
    return (
      <main className="min-h-screen bg-gray-950 text-white">
        <div className="max-w-lg mx-auto px-6 py-16">
          <div className="text-center mb-8">
            <div className="text-5xl mb-4">🔐</div>
            <h1 className="text-3xl font-bold mb-2">
              {locale === "el" ? "Επαλήθευση Επιτυχής!" : "Verification Successful!"}
            </h1>
          </div>

          {/* WARNING */}
          <div className="bg-red-950 border border-red-700 rounded-2xl p-6 mb-6">
            <h2 className="font-bold text-red-300 mb-2">
              ⚠️ {locale === "el" ? "ΣΗΜΑΝΤΙΚΟ — Αποθηκεύστε το κλειδί σας" : "IMPORTANT — Save your key"}
            </h2>
            <p className="text-red-200 text-sm mb-4">
              {locale === "el"
                ? "Αυτό το κλειδί εμφανίζεται ΜΟΝΟ ΜΙΑ ΦΟΡΑ. Δεν αποθηκεύεται στον server. Αν το χάσετε, πρέπει να κάνετε revoke + νέα επαλήθευση."
                : "This key is shown ONLY ONCE. It is not stored on the server. If you lose it, you must revoke + re-verify."}
            </p>
            <div className="bg-gray-900 rounded-xl p-4 font-mono text-sm break-all text-yellow-300 mb-3">
              {privateKey}
            </div>
            <button
              onClick={copyKey}
              className="px-4 py-2 bg-red-700 hover:bg-red-600 rounded-lg font-semibold text-sm transition-colors"
            >
              {copied
                ? (locale === "el" ? "✓ Αντιγράφηκε!" : "✓ Copied!")
                : (locale === "el" ? "📋 Αντιγραφή Κλειδιού" : "📋 Copy Key")}
            </button>
          </div>

          {/* Nullifier Info */}
          <div className="bg-gray-900 rounded-2xl p-6 mb-6 border border-gray-800">
            <h3 className="font-semibold mb-2 text-gray-300">Nullifier Hash</h3>
            <p className="text-xs font-mono text-gray-500 break-all mb-3">{nullifier}</p>
            <p className="text-gray-400 text-sm">
              {locale === "el"
                ? "Αυτό το hash αποθηκεύτηκε τοπικά. Χρησιμοποιείται για να εμποδίσει διπλή ψηφοφορία χωρίς να αποκαλύπτει την ταυτότητά σας."
                : "This hash is stored locally. It prevents double voting without revealing your identity."}
            </p>
          </div>

          {/* CTA */}
          <div className="text-center">
            <Link
              href={`/${locale}/bills`}
              className="inline-block px-8 py-3 bg-blue-600 hover:bg-blue-500 rounded-xl font-semibold transition-colors"
            >
              🏛️ {locale === "el" ? "Ψηφίστε τώρα" : "Vote now"} →
            </Link>
          </div>
        </div>
      </main>
    );
  }

  // ── FORM ──────────────────────────────────────────────────────────────────
  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-lg mx-auto px-6 py-16">
        <div className="text-center mb-10">
          <div className="text-5xl mb-4">🔐</div>
          <h1 className="text-3xl font-bold mb-2">
            {locale === "el" ? "Επαλήθευση Ταυτότητας" : "Identity Verification"}
          </h1>
          <p className="text-gray-400">
            {locale === "el"
              ? "Μία φορά — Ανώνυμα — Ασφαλώς"
              : "Once — Anonymous — Secure"}
          </p>
        </div>

        {/* Privacy Note */}
        <div className="bg-green-950 border border-green-800 rounded-2xl p-5 mb-8 text-sm text-green-300">
          <p className="font-semibold mb-1">
            🔒 {locale === "el" ? "Απόρρητο" : "Privacy"}
          </p>
          <p>
            {locale === "el"
              ? "Ο αριθμός σας διαγράφεται αμέσως μετά τη δημιουργία του κλειδιού. Δεν αποθηκεύεται ποτέ."
              : "Your number is deleted immediately after key generation. It is never stored."}
          </p>
        </div>

        <form onSubmit={handleVerify} className="space-y-6">
          {/* Phone */}
          <div>
            <label className="block text-sm font-semibold mb-2 text-gray-300">
              {locale === "el" ? "Ελληνικός αριθμός κινητού" : "Greek mobile number"}
            </label>
            <input
              type="tel"
              value={phone}
              onChange={e => setPhone(e.target.value)}
              placeholder="+306912345678"
              required
              className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white placeholder-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-colors"
            />
          </div>

          {/* Region */}
          <div>
            <label className="block text-sm font-semibold mb-2 text-gray-300">
              {locale === "el" ? "Περιφέρεια (προαιρετικά)" : "Region (optional)"}
            </label>
            <select
              value={region}
              onChange={e => setRegion(e.target.value)}
              className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:border-blue-500 outline-none transition-colors"
            >
              {REGIONS.map(r => (
                <option key={r.value} value={r.value}>
                  {locale === "el" ? r.label_el : r.label_en}
                </option>
              ))}
            </select>
          </div>

          {/* Gender */}
          <div>
            <label className="block text-sm font-semibold mb-2 text-gray-300">
              {locale === "el" ? "Φύλο (προαιρετικά)" : "Gender (optional)"}
            </label>
            <select
              value={gender}
              onChange={e => setGender(e.target.value)}
              className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white focus:border-blue-500 outline-none transition-colors"
            >
              <option value="GENDER_NO_ANSWER">{locale === "el" ? "Δεν απαντώ" : "Prefer not to say"}</option>
              <option value="GENDER_MALE">{locale === "el" ? "Άνδρας" : "Male"}</option>
              <option value="GENDER_FEMALE">{locale === "el" ? "Γυναίκα" : "Female"}</option>
              <option value="GENDER_DIVERSE">{locale === "el" ? "Άλλο" : "Other"}</option>
            </select>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-red-900/50 border border-red-700 rounded-xl p-4 text-red-300 text-sm">
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading || !phone}
            className="w-full py-4 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-xl font-bold text-lg transition-colors"
          >
            {loading
              ? (locale === "el" ? "Επαλήθευση..." : "Verifying...")
              : (locale === "el" ? "🔐 Επαλήθευση" : "🔐 Verify")}
          </button>
        </form>

        {/* How it works */}
        <div className="mt-10 bg-gray-900 rounded-2xl p-6 border border-gray-800">
          <h3 className="font-semibold mb-4 text-gray-300">
            {locale === "el" ? "Πώς λειτουργεί;" : "How it works"}
          </h3>
          <div className="space-y-3 text-sm text-gray-400">
            <p>1️⃣ {locale === "el"
              ? "Ελέγχεται αν ο αριθμός σας είναι πραγματικός ελληνικός κινητός (HLR Lookup)"
              : "Your number is checked to verify it's a real Greek mobile (HLR Lookup)"}</p>
            <p>2️⃣ {locale === "el"
              ? "Δημιουργείται ένα κρυπτογραφικό ζεύγος κλειδιών Ed25519"
              : "A cryptographic Ed25519 key pair is generated"}</p>
            <p>3️⃣ {locale === "el"
              ? "Ο αριθμός σας διαγράφεται αμέσως — μόνο ένα hash αποθηκεύεται"
              : "Your number is deleted immediately — only a hash is stored"}</p>
            <p>4️⃣ {locale === "el"
              ? "Το ιδιωτικό κλειδί σας εμφανίζεται ΜΙΑ ΦΟΡΑ — αποθηκεύστε το!"
              : "Your private key is shown ONCE — save it!"}</p>
          </div>
        </div>
      </div>
    </main>
  );
}
