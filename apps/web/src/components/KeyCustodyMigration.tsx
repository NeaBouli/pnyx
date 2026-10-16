"use client";

import { useEffect } from "react";

import { migrateLegacyWebKey } from "@/lib/keystore";

/**
 * EVA-003 PR5: moves a legacy plaintext identity key into non-extractable
 * WebCrypto custody in the background. Renders nothing; never blocks the page;
 * only acts when the API advertises `features.identity_key_check`.
 */
export default function KeyCustodyMigration() {
  useEffect(() => {
    void migrateLegacyWebKey().catch(() => {});
  }, []);
  return null;
}
