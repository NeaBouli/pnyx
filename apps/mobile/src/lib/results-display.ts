/** Null is withheld data, including complementary suppression; never show zero. */
export function publicVoteCount(count: number | null, k = 10): string {
  return count === null ? `λιγότερες από ${k} ψήφοι` : String(count);
}

export function publicVoteShare(count: number | null, percent: number | null): string {
  return count === null || percent === null ? "—" : `${count} (${percent}%)`;
}
