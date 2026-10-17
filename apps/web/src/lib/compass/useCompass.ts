/**
 * useCompass — React Hook for Liquid Political Compass.
 * Loads/saves encrypted profile, computes results reactively.
 */
"use client";

import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import type { CompassProfile, CompassModel, CompassResult } from "./types";
import { createEmptyProfile, seedFromVAA, recordBillVote, computeResult, getDataPointCount } from "./engine";
import { loadProfile, saveProfile, clearProfile as clearStorage, CompassStorageError, type CompassKeys } from "./storage";
import { readCompassKeys, withKeystoreLock } from "../keystore";

interface PartyData {
  parties: Record<string, {
    id: number;
    nameEl: string;
    colorHex: string;
    positions: Record<string, number>;
  }>;
  statementCategories: Record<string, string>;
}

let cachedPartyData: PartyData | null = null;

async function getPartyData(): Promise<PartyData | null> {
  if (cachedPartyData) return cachedPartyData;
  try {
    const res = await fetch("/data/party-positions.json");
    if (!res.ok) return null;
    cachedPartyData = await res.json();
    return cachedPartyData;
  } catch {
    return null;
  }
}

/**
 * Leitet das Kompass-Ergebnis aus Profil und Parteidaten ab.
 * Rein berechnend — identisch zur bisherigen Effekt-Logik.
 */
export function deriveCompassResult(
  profile: CompassProfile,
  partyData: PartyData | null
): CompassResult | null {
  if (!profile.selectedModel || getDataPointCount(profile) === 0) {
    return null;
  }

  if (profile.selectedModel === "party-match" && partyData) {
    const partyPositions: Record<string, Record<number, number>> = {};
    const partyMeta: Record<string, { id: number; nameEl: string; colorHex: string }> = {};
    for (const [abbr, data] of Object.entries(partyData.parties)) {
      const numPositions: Record<number, number> = {};
      for (const [k, v] of Object.entries(data.positions)) {
        numPositions[Number(k)] = v;
      }
      partyPositions[abbr] = numPositions;
      partyMeta[abbr] = { id: data.id, nameEl: data.nameEl, colorHex: data.colorHex };
    }
    return computeResult(profile, "party-match", partyPositions, partyMeta);
  }

  return computeResult(profile, profile.selectedModel);
}

/**
 * EVA-003: the non-extractable Compass key once migrated, else the legacy
 * identity key. A failed IndexedDB read REJECTS (it must not look like "no
 * key"): callers then neither load nor save, so stored data stays untouched.
 */
export async function readCompassKeysSafely(): Promise<CompassKeys> {
  return readCompassKeys();
}

export function saveProfileSafely(p: CompassProfile, keys: string | CompassKeys | null): Promise<void> {
  return saveProfile(p, keys).catch((error: unknown) => {
    if (!(error instanceof CompassStorageError)) console.warn("[compass] profile save failed", error);
  });
}

export function useCompass() {
  const [profile, setProfile] = useState<CompassProfile>(createEmptyProfile());
  const [loading, setLoading] = useState(true);
  const [partyData, setPartyData] = useState<PartyData | null>(null);
  const saveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Schlüssel für die Verschlüsselung (EVA-003: eigener Compass-Key oder Legacy)
  const getKeys = useCallback((): Promise<CompassKeys> => readCompassKeysSafely(), []);

  // Profil laden
  useEffect(() => {
    async function init() {
      try {
        const [loaded, pd] = await Promise.all([
          // EVA-003: load (incl. its implicit plaintext migration save) under
          // the cross-tab keystore lock, keys read inside it.
          withKeystoreLock(async () => loadProfile(await getKeys())).then(
            async (locked) => (locked ? locked.value : loadProfile(await getKeys())),
          ),
          getPartyData(),
        ]);
        setProfile(loaded);
        setPartyData(pd);
      } catch {
        setProfile(createEmptyProfile()); // Laden fehlgeschlagen — leeres Profil, kein Klartext
      } finally {
        setLoading(false);
      }
    }
    init();
  }, [getKeys]);

  // Profil speichern (debounced)
  const persistProfile = useCallback((p: CompassProfile) => {
    if (saveTimeout.current) clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(() => {
      // EVA-003: serialised with the key migration in every tab; keys are
      // read inside the lock so a legacy-key write can never land after the
      // migration moved the profile to the new key.
      void (async () => {
        const locked = await withKeystoreLock(async () => saveProfileSafely(p, await getKeys()));
        if (!locked) await saveProfileSafely(p, await getKeys());
      })().catch(() => {});
    }, 300);
  }, [getKeys]);

  // Ergebnis bei Profil/Modell-Änderung berechnen (abgeleitet, kein Effekt)
  const result = useMemo(
    () => deriveCompassResult(profile, partyData),
    [profile, partyData]
  );

  // ─── Actions ──────────────────────────────────────────────────────────

  const setModel = useCallback((model: CompassModel | null) => {
    const updated = { ...profile, selectedModel: model, updatedAt: new Date().toISOString() };
    setProfile(updated);
    persistProfile(updated);
  }, [profile, persistProfile]);

  const doSeedFromVAA = useCallback((answers: Record<number, number>) => {
    if (!partyData) return;
    const categories: Record<number, string> = {};
    for (const [k, v] of Object.entries(partyData.statementCategories)) {
      categories[Number(k)] = v;
    }
    const updated = seedFromVAA(profile, answers, categories);
    setProfile(updated);
    persistProfile(updated);
  }, [profile, partyData, persistProfile]);

  const doRecordBillVote = useCallback((billId: string, vote: string, categories: string[]) => {
    if (!profile.selectedModel) return; // Kompass deaktiviert
    const normalizedVote = vote.toUpperCase() as "YES" | "NO" | "ABSTAIN";
    const updated = recordBillVote(profile, billId, normalizedVote, categories);
    setProfile(updated);
    persistProfile(updated);
  }, [profile, persistProfile]);

  const reset = useCallback(() => {
    clearStorage();
    const empty = createEmptyProfile();
    setProfile(empty);
  }, []);

  return {
    profile,
    result,
    loading,
    isEnabled: profile.selectedModel !== null,
    selectedModel: profile.selectedModel,
    dataPoints: getDataPointCount(profile),
    vaaCompleted: profile.vaaCompletedAt !== null,
    billVoteCount: profile.billVotes.length,

    setModel,
    seedFromVAA: doSeedFromVAA,
    recordBillVote: doRecordBillVote,
    clearProfile: reset,
  };
}
