import * as SecureStore from "expo-secure-store";
import type { CompassResult, Answer } from "../../../../packages/compass/src/types";

const KEY = "compass_data";

interface StoredData {
  result: CompassResult | null;
  answers: Answer[];
}

export async function saveCompass(result: CompassResult, answers: Answer[]): Promise<void> {
  await SecureStore.setItemAsync(KEY, JSON.stringify({ result, answers }));
}

export async function getCompass(): Promise<StoredData> {
  const raw = await SecureStore.getItemAsync(KEY);
  if (!raw) return { result: null, answers: [] };
  try { return JSON.parse(raw); } catch { return { result: null, answers: [] }; }
}

export async function getResult(): Promise<CompassResult | null> {
  return (await getCompass()).result;
}

export async function clearCompass(): Promise<void> {
  await SecureStore.deleteItemAsync(KEY);
}
