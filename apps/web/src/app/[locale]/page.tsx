import { useTranslations } from "next-intl";
import Link from "next/link";

export default function HomePage() {
  const t = useTranslations("home");
  const tCommon = useTranslations("common");

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 py-24 text-center">
        <h1 className="text-6xl font-bold mb-4 text-blue-400 tracking-tight">
          {t("title")}
        </h1>
        <p className="text-xl text-gray-300 mb-4">
          {t("subtitle")}
        </p>
        <p className="text-gray-400 mb-12 max-w-2xl mx-auto leading-relaxed">
          {t("description")}
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="vaa"
            className="px-8 py-4 bg-blue-600 hover:bg-blue-500 rounded-xl font-semibold text-lg transition-colors"
          >
            {t("start_vaa")} →
          </Link>
          <Link
            href="bills"
            className="px-8 py-4 bg-gray-800 hover:bg-gray-700 rounded-xl font-semibold text-lg transition-colors border border-gray-700"
          >
            {t("see_bills")}
          </Link>
        </div>
      </section>

      {/* Feature Cards */}
      <section className="max-w-5xl mx-auto px-6 pb-16 grid grid-cols-1 md:grid-cols-3 gap-6">
        {[
          {
            icon: "🗳️",
            title: "Wahlkompass",
            desc: "15 θέσεις · 8 κόμματα · Άμεσο αποτέλεσμα",
          },
          {
            icon: "🏛️",
            title: "Κοινοβούλιο",
            desc: "Ψηφίστε για πραγματικά νομοσχέδια της Βουλής",
          },
          {
            icon: "🔐",
            title: "Ανωνυμία",
            desc: "Ed25519 · Nullifier Hash · Καμία αποθήκευση προσωπικών δεδομένων",
          },
        ].map((card) => (
          <div
            key={card.title}
            className="bg-gray-900 border border-gray-800 rounded-2xl p-6 hover:border-blue-800 transition-colors"
          >
            <div className="text-3xl mb-3">{card.icon}</div>
            <h3 className="font-bold text-lg mb-2">{card.title}</h3>
            <p className="text-gray-400 text-sm leading-relaxed">{card.desc}</p>
          </div>
        ))}
      </section>

      {/* Disclaimer + Footer */}
      <footer className="border-t border-gray-800 px-6 py-8 text-center text-sm text-gray-500">
        <p className="mb-2">{t("disclaimer")}</p>
        <p>
          {tCommon("copyright")} ·{" "}
          <a
            href="https://github.com/NeaBouli/pnyx"
            className="hover:text-gray-300 transition-colors"
            target="_blank"
            rel="noopener noreferrer"
          >
            {tCommon("open_source")}
          </a>
        </p>
      </footer>
    </main>
  );
}
