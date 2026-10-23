/** Parliament imports retain their canonical source URL; the model's legacy
 * PARLIAMENT default alone is not evidence of provenance (admin proposals used it).
 * HTTP originals establish provenance, but are never offered as trusted links.
 */
type ParliamentSource = {
  official_source_url?: string | null;
  parliament_url?: string | null;
};

function parliamentUrl(value?: string | null): URL | null {
  if (!value || !/^https?:\/\//i.test(value) || /[\\\s]/.test(value)) return null;
  try {
    const url = new URL(value);
    const authority = value.split("/")[2];
    if (!["https:", "http:"].includes(url.protocol)
      || !["www.hellenicparliament.gr", "hellenicparliament.gr"].includes(url.hostname)
      || url.username || url.password || url.port || authority.includes("@") || authority.includes(":")) return null;
    return url;
  } catch {
    return null;
  }
}

export function hasParliamentProvenance(bill: ParliamentSource): boolean {
  return !!(parliamentUrl(bill.official_source_url) || parliamentUrl(bill.parliament_url));
}

export function parliamentOriginalUrl(bill: ParliamentSource): string | null {
  const value = bill.official_source_url || bill.parliament_url;
  return parliamentUrl(value)?.protocol === "https:" ? value! : null;
}
