"use client";

import Link from "next/link";
import { useLocale } from "next-intl";
import { usePathname } from "next/navigation";

const ITEMS = [
  { path: "bills", el: "Νομοσχέδια", en: "Bills" },
  { path: "results", el: "Αποτελέσματα", en: "Results" },
  { path: "mp", el: "Κόμματα", en: "Parties" },
  { path: "municipal", el: "Δήμοι", en: "Municipal" },
  { path: "analytics", el: "Αναλυτικά", en: "Analytics" },
] as const;

export default function PublicDataNav() {
  const locale = useLocale();
  const pathname = usePathname();

  return (
    <nav aria-label={locale === "el" ? "Δημόσια δεδομένα" : "Public data"}
      className="mb-6 overflow-x-auto">
      <div className="flex min-w-max gap-1 rounded-lg border border-gray-200 bg-white p-1">
        {ITEMS.map((item) => {
          const href = `/${locale}/${item.path}`;
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link key={item.path} href={href} aria-current={active ? "page" : undefined}
              className={`rounded-md px-3 py-2 text-sm font-semibold transition-colors ${
                active
                  ? "bg-blue-600 text-white"
                  : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"
              }`}>
              {locale === "el" ? item.el : item.en}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
