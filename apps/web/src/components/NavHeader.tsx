"use client";

import Link from "next/link";
import { useLocale } from "next-intl";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";

export default function NavHeader() {
  const locale = useLocale();
  const path = usePathname();

  const navLinks = [
    { href: `/${locale}`,        label_el: "Αρχική",       label_en: "Home"    },
    { href: `/${locale}/vaa`,    label_el: "Πολιτική Πυξίδα",  label_en: "Political Compass" },
    { href: `/${locale}/bills`,  label_el: "Νομοσχέδια",  label_en: "Bills"   },
    { href: `/${locale}/compass`, label_el: "Πυξίδα",     label_en: "Compass" },
    { href: `/${locale}/verify`, label_el: "Επαλήθευση",  label_en: "Verify"  },
  ];

  const otherLocale = locale === "el" ? "en" : "el";
  const otherPath   = path.replace(`/${locale}`, `/${otherLocale}`);

  return (
    <header className="border-b border-gray-800 px-6 py-4 flex justify-between items-center sticky top-0 bg-gray-950/95 backdrop-blur-sm z-50">
      <Link href={`/${locale}`} className="text-blue-400 font-bold text-xl tracking-tight">
        εκκλησία
      </Link>

      <nav className="hidden sm:flex gap-1">
        {navLinks.map(link => (
          <Link
            key={link.href}
            href={link.href}
            className={clsx(
              "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              path === link.href || path.startsWith(link.href + "/")
                ? "bg-blue-900 text-blue-300"
                : "text-gray-400 hover:text-white hover:bg-gray-800"
            )}
          >
            {locale === "el" ? link.label_el : link.label_en}
          </Link>
        ))}
      </nav>

      <div className="flex items-center gap-3">
        <Link
          href={otherPath}
          className="text-sm text-gray-500 hover:text-gray-300 transition-colors px-2 py-1 rounded-lg hover:bg-gray-800"
        >
          {otherLocale.toUpperCase()}
        </Link>
        <a
          href="https://github.com/NeaBouli/pnyx"
          target="_blank"
          rel="noopener noreferrer"
          className="text-gray-500 hover:text-gray-300 transition-colors"
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
