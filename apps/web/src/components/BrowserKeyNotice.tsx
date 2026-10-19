"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import { readLocalIdentityKeyState } from "@/lib/keystore";

/** T-9154 draft slice. The server's runtime flag defaults to off. */
export default function BrowserKeyNotice({ enabled = false }: { enabled?: boolean }) {
  const t = useTranslations("identity");
  const pathname = usePathname();
  const [absent, setAbsent] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    let disposed = false;
    let attempt = 0;
    const check = async () => {
      const current = ++attempt;
      // Defensive catch: a failed check must never announce key loss.
      const state = await readLocalIdentityKeyState().catch(() => "unavailable");
      if (!disposed && current === attempt) setAbsent(state === "absent");
    };
    const onForeground = () => {
      if (document.visibilityState === "visible") void check();
    };
    void check();
    window.addEventListener("storage", onForeground);
    document.addEventListener("visibilitychange", onForeground);
    return () => {
      disposed = true;
      window.removeEventListener("storage", onForeground);
      document.removeEventListener("visibilitychange", onForeground);
    };
  }, [enabled, pathname]);

  if (!enabled || !absent) return null;
  return (
    <aside role="status" className="border-b border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
      <a href="/embed/qr-login.html" className="underline underline-offset-2">
        {t("key_not_on_browser")}
      </a>
    </aside>
  );
}
