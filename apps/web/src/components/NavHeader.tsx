"use client";

import Link from "next/link";
import Image from "next/image";
import { useLocale } from "next-intl";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";

export default function NavHeader() {
  const locale = useLocale();
  const path = usePathname();

  const navLinks = [
    { href: "https://ekklesia.gr", label_el: "Αρχική",      label_en: "Home",    external: true },
    { href: `/${locale}/bills`,    label_el: "Νομοσχέδια",  label_en: "Bills",   external: false },
    { href: `/${locale}/results`,  label_el: "Αποτελέσματα", label_en: "Results", external: false },
  ];

  const otherLocale = locale === "el" ? "en" : "el";
  const otherPath = path.replace(`/${locale}`, `/${otherLocale}`);

  return (
    <header className="border-b border-gray-200 bg-white/95 backdrop-blur-sm px-6 py-3 flex justify-between items-center sticky top-0 z-50">
      <a href="https://ekklesia.gr" className="flex items-center gap-2 group">
        <Image src="/pnx.png" alt="εκκλησία του έθνους" width={40} height={40} className="rounded-lg" />
        <span className="text-blue-600 font-black text-xl tracking-tight group-hover:text-blue-700 transition-colors">
          εκκλησία<span className="text-gray-400 font-normal ml-1" style={{ fontSize: "0.55em", letterSpacing: "0.05em" }}>του έθνους</span>
        </span>
      </a>

      <nav className="hidden sm:flex gap-1">
        {navLinks.map(link => {
          const isActive = !link.external && (path === link.href || path.startsWith(link.href + "/"));
          const cls = clsx(
            "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
            isActive ? "bg-blue-50 text-blue-700" : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
          );
          return link.external ? (
            <a key={link.href} href={link.href} className={cls}>
              {locale === "el" ? link.label_el : link.label_en}
            </a>
          ) : (
            <Link key={link.href} href={link.href} className={cls}>
              {locale === "el" ? link.label_el : link.label_en}
            </Link>
          );
        })}
      </nav>

      <div className="flex items-center gap-3">
        <Link
          href={otherPath}
          className="text-sm font-semibold text-gray-500 hover:text-blue-600 transition-colors px-2 py-1 rounded-lg hover:bg-blue-50"
        >
          {otherLocale.toUpperCase()}
        </Link>
        <a
          href="https://github.com/NeaBouli/pnyx"
          target="_blank"
          rel="noopener noreferrer"
          className="text-gray-400 hover:text-gray-600 transition-colors"
          title="GitHub"
        >
          <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
          </svg>
        </a>
      </div>
    </header>
  );
}
