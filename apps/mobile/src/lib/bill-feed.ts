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

export function prioritizeBillsPage<T extends { id?: string | null }>(
  primary: T[],
  secondary: T[],
  limit = DEFAULT_FEED_LIMIT,
): { items: T[]; secondaryConsumed: number } {
  const seen = new Set<string>();
  const items: T[] = [];
  for (const bill of primary) {
    if (!bill?.id || seen.has(bill.id)) continue;
    seen.add(bill.id);
    items.push(bill);
    if (items.length >= limit) return { items, secondaryConsumed: 0 };
  }

  let secondaryConsumed = 0;
  for (const bill of secondary) {
    secondaryConsumed += 1;
    if (!bill?.id || seen.has(bill.id)) continue;
    seen.add(bill.id);
    items.push(bill);
    if (items.length >= limit) break;
  }
  return { items, secondaryConsumed };
}
