"use client";

import { useEffect } from "react";

import { migrateLegacyWebKey, rotateMigratedWebKey } from "@/lib/keystore";

/**
 * EVA-003 PR5/PR6: migrate custody, then replace the once-exposed key with a
 * fresh device key. Flags gate new rotations, never journal recovery. Retry
 * transient failures with backoff and on foreground/online.
 */
export default function KeyCustodyMigration() {
  useEffect(() => {
    let busy = false;
    let retry = true;
    let lastAttempt = -Infinity;
    let disposed = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let delay = 60_000;
    const run = async () => {
      if (disposed || busy || !retry || Date.now() - lastAttempt < 60_000) return;
      clearTimeout(retryTimer);
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
      } catch {
        retry = true;
      } finally {
        busy = false;
        if (!disposed && retry) {
          retryTimer = setTimeout(() => { void run(); }, delay);
          delay = Math.min(delay * 2, 15 * 60_000);
        }
      }
    };
    const onForeground = () => {
      if (document.visibilityState === "visible") void run();
    };
    void run();
    window.addEventListener("online", onForeground);
    document.addEventListener("visibilitychange", onForeground);
    return () => {
      disposed = true;
      clearTimeout(retryTimer);
      window.removeEventListener("online", onForeground);
      document.removeEventListener("visibilitychange", onForeground);
    };
  }, []);
  return null;
}
