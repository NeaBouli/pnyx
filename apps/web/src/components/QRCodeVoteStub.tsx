"use client";

import { useLocale } from "next-intl";

export default function QRCodeVoteStub() {
  const locale = useLocale();
  const isEl = locale === "el";

  return (
    <div className="bg-blue-50 rounded-2xl p-8 border border-blue-200 text-center">
      {/* Placeholder QR icon */}
      <div className="w-24 h-24 bg-white rounded-2xl border-2 border-dashed border-blue-300 flex items-center justify-center mx-auto mb-4">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#93c5fd" strokeWidth="1.5">
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="3" height="3" />
          <rect x="18" y="18" width="3" height="3" />
          <rect x="18" y="14" width="3" height="1" />
          <rect x="14" y="18" width="1" height="3" />
        </svg>
      </div>

      <p className="text-blue-800 font-semibold text-lg mb-2">
        {isEl ? "Ψηφίστε μέσω QR Code" : "Vote via QR Code"}
      </p>
      <p className="text-blue-600 text-sm mb-6 max-w-sm mx-auto leading-relaxed">
        {isEl
          ? "Σύντομα θα μπορείτε να σκανάρετε έναν κωδικό QR με την εφαρμογή εκκλησία για να ψηφίσετε απευθείας από τον browser."
          : "Soon you will be able to scan a QR code with the ekklesia app to vote directly from the browser."}
      </p>
      <a
        href="https://ekklesia.gr/#download"
        className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold text-sm transition-all shadow-sm hover:shadow-md"
      >
        {isEl ? "Κατεβάστε την εφαρμογή" : "Download the app"}
      </a>
    </div>
  );
}
