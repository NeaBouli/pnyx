/**
 * useCompass — React Hook for Liquid Political Compass.
 * Loads/saves encrypted profile, computes results reactively.
 */
"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import type { CompassProfile, CompassModel, CompassResult } from "./types";
import { createEmptyProfile, seedFromVAA, recordBillVote, computeResult, getDataPointCount } from "./engine";
import { loadProfile, saveProfile, clearProfile as clearStorage } from "./storage";
import { loadKeypair } from "../crypto";

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

export function useCompass() {
  const [profile, setProfile] = useState<CompassProfile>(createEmptyProfile());
  const [result, setResult] = useState<CompassResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [partyData, setPartyData] = useState<PartyData | null>(null);
  const saveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Private Key für Verschlüsselung
  const getPrivateKey = useCallback((): string | null => {
    const kp = loadKeypair();
    return kp?.privateKeyHex ?? null;
  }, []);

  // Profil laden
  useEffect(() => {
    async function init() {
      const [loaded, pd] = await Promise.all([
        loadProfile(getPrivateKey()),
        getPartyData(),
      ]);
      setProfile(loaded);
      setPartyData(pd);
      setLoading(false);
    }
    init();
  }, [getPrivateKey]);

  // Profil speichern (debounced)
  const persistProfile = useCallback((p: CompassProfile) => {
    if (saveTimeout.current) clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(() => {
      saveProfile(p, getPrivateKey());
    }, 300);
  }, [getPrivateKey]);

  // Ergebnis bei Profil/Modell-Änderung berechnen
  useEffect(() => {
    if (!profile.selectedModel || getDataPointCount(profile) === 0) {
      setResult(null);
      return;
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
      setResult(computeResult(profile, "party-match", partyPositions, partyMeta));
    } else {
      setResult(computeResult(profile, profile.selectedModel));
    }
  }, [profile, partyData]);

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
    setResult(null);
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
