"use client";

import { useEffect } from "react";

import { migrateLegacyWebKey, rotateMigratedWebKey } from "@/lib/keystore";

/**
 * EVA-003 PR5/PR6: migrate custody, then replace the once-exposed key with a
 * fresh device key. Each operation checks its server feature flags. Retry
 * transient failures on foreground/online, throttled to once per minute.
 */
export default function KeyCustodyMigration() {
  useEffect(() => {
    let busy = false;
    let retry = true;
    let lastAttempt = -Infinity;
    const run = async () => {
      if (busy || !retry || Date.now() - lastAttempt < 60_000) return;
      busy = true;
      lastAttempt = Date.now();
      try {
        const migration = await migrateLegacyWebKey();
        if (migration !== "migrated" && migration !== "not_needed") {
          retry = migration === "retry_later";
          return;
        }
        const rotation = await rotateMigratedWebKey();
        retry = rotation === "retry_later";
        if (rotation === "rotated" || rotation === "already_rotated" || rotation === "conflict") {
          console.info("[keystore] identity rotation", rotation); // outcome only
        }
      } finally {
        busy = false;
      }
    };
    const onForeground = () => {
      if (document.visibilityState === "visible") void run();
    };
    void run();
    window.addEventListener("online", onForeground);
    document.addEventListener("visibilitychange", onForeground);
    return () => {
      window.removeEventListener("online", onForeground);
      document.removeEventListener("visibilitychange", onForeground);
    };
  }, []);
  return null;
}
