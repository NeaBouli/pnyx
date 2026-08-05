const PHONE_SEPARATORS = /[\s().-]/g;
const PHONE_INPUT_CHARACTERS = /^[+\d\s().-]+$/;
const GREEK_MOBILE_LOCAL = /^0?69\d{8}$/;

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
  if (!PHONE_INPUT_CHARACTERS.test(raw)) return null;

  const compact = raw.replace(PHONE_SEPARATORS, "");
  const direct = canonicalizeGreekMobile(compact);
  if (direct) return direct;

  if (compact.startsWith("+30")) {
    return canonicalizeGreekMobile(compact.slice(3));
  }

  return null;
}
