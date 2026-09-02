const PHONE_SEPARATORS = /[\s().-]/g;
const PHONE_INPUT_CHARACTERS = /^[+\d\s().-]+$/;
const GREEK_MOBILE_LOCAL = /^0?69\d{8}$/;
const INVISIBLE_PHONE_MARKS = /[\u061C\u200B-\u200F\u202A-\u202E\u2060-\u2064\u2066-\u2069\uFEFF]/g;
const UNICODE_PHONE_DASHES = /[\u2010-\u2015\u2212\uFE63\uFF0D]/g;

function mapDigitRange(value: string, rangeStart: number): string {
  return String(value.charCodeAt(0) - rangeStart);
}

/**
 * Removes direction/clipboard markers and converts common OEM keyboard
 * variants to the ASCII characters accepted by the verification API.
 */
export function sanitizeGreekMobileInput(raw: string): string {
  return raw
    .replace(INVISIBLE_PHONE_MARKS, "")
    .replace(/\uFF0B/g, "+")
    .replace(UNICODE_PHONE_DASHES, "-")
    .replace(/[０-９]/g, value => mapDigitRange(value, 0xFF10))
    .replace(/[٠-٩]/g, value => mapDigitRange(value, 0x0660))
    .replace(/[۰-۹]/g, value => mapDigitRange(value, 0x06F0));
}

function canonicalizeGreekMobile(compact: string): string | null {
  let local = compact;

  if (compact.startsWith("+30")) {
    local = compact.slice(3);
  } else if (compact.startsWith("0030")) {
    local = compact.slice(4);
  } else if (compact.startsWith("30")) {
    local = compact.slice(2);
  }

  if (!GREEK_MOBILE_LOCAL.test(local)) return null;
  return `+30${local.replace(/^0/, "")}`;
}

/**
 * Converts supported Greek mobile formats to +3069XXXXXXXX.
 * The fallback handles a full number pasted after the field's prefilled +30.
 */
export function normalizeGreekMobileInput(raw: string): string | null {
  const sanitized = sanitizeGreekMobileInput(raw);
  if (!PHONE_INPUT_CHARACTERS.test(sanitized)) return null;

  const compact = sanitized.replace(PHONE_SEPARATORS, "");
  const direct = canonicalizeGreekMobile(compact);
  if (direct) return direct;

  if (compact.startsWith("+30")) {
    return canonicalizeGreekMobile(compact.slice(3));
  }

  return null;
}
