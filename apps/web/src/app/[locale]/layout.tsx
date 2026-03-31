import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import NavHeader from "@/components/NavHeader";
import "../globals.css";

const inter = Inter({ subsets: ["latin", "greek"] });

export const metadata: Metadata = {
  title: "εκκλησία — Ekklesia.gr",
  description: "Ψηφιακή Πλατφόρμα Αμέσης Δημοκρατίας για τον Έλληνα Πολίτη",
  keywords: ["democracy", "greece", "parliament", "voting", "δημοκρατία"],
  authors: [{ name: "Vendetta Labs", url: "https://github.com/NeaBouli" }],
  manifest: "/manifest.json",
  themeColor: "#2563eb",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "εκκλησία",
  },
  openGraph: {
    title: "εκκλησία — Ekklesia.gr",
    description: "Digital Direct Democracy Platform for Greek Citizens",
    locale: "el_GR",
    alternateLocale: "en_US",
    type: "website",
  },
};

export default async function LocaleLayout({
  children,
  params: { locale },
}: {
  children: React.ReactNode;
  params: { locale: string };
}) {
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <head>
        <link rel="apple-touch-icon" href="/pnx.png" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
      </head>
      <body className={inter.className}>
        <NextIntlClientProvider messages={messages}>
          <NavHeader />
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
