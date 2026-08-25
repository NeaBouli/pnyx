export type JsonRecord = Record<string, unknown>

export function asRecord(value: unknown): JsonRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonRecord
    : null
}

export function arrayFrom<T>(value: unknown, ...keys: string[]): T[] {
  if (Array.isArray(value)) return value as T[]

  const record = asRecord(value)
  if (!record) return []

  for (const key of keys) {
    const candidate = record[key]
    if (Array.isArray(candidate)) return candidate as T[]
  }

  return []
}

export function numberFrom(value: unknown, fallback: number | null = null): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}
