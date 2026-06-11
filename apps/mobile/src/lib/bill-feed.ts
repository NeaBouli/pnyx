const DEFAULT_FEED_LIMIT = 10;

export function mergeBillsUnique<T extends { id?: string | null }>(
  primary: T[],
  secondary: T[],
  limit = DEFAULT_FEED_LIMIT,
): T[] {
  const seen = new Set<string>();
  const merged: T[] = [];
  for (const bill of [...primary, ...secondary]) {
    if (!bill?.id || seen.has(bill.id)) continue;
    seen.add(bill.id);
    merged.push(bill);
    if (merged.length >= limit) break;
  }
  return merged;
}
