/** Attribution requires both the Parliament workflow source and an official HTTPS
 * URL. Admin proposals keep the PARLIAMENT default without implying provenance.
 */
type ParliamentSource = {
  source?: string | null;
  official_source_url?: string | null;
  parliament_url?: string | null;
};

function parliamentUrl(value?: string | null): URL | null {
  if (!value || !/^https:\/\//i.test(value) || /[\\\s\u0000-\u001f\u007f]/.test(value)) return null;
  try {
    const url = new URL(value);
    const authority = value.slice("https://".length).split(/[/?#]/)[0];
    if (url.protocol !== "https:"
      || !["www.hellenicparliament.gr", "hellenicparliament.gr"].includes(url.hostname)
      || url.username || url.password || url.port || authority.toLowerCase() !== url.hostname) return null;
    return url;
  } catch {
    return null;
  }
}

export function hasParliamentProvenance(bill: ParliamentSource): boolean {
  return parliamentOriginalUrl(bill) !== null;
}

export function parliamentOriginalUrl(bill: ParliamentSource): string | null {
  if (bill.source !== "PARLIAMENT") return null;
  for (const value of [bill.official_source_url, bill.parliament_url]) {
    if (parliamentUrl(value)) return value!;
  }
  return null;
}
