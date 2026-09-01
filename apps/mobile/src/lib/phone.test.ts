import { describe, expect, it } from "vitest";
import { normalizeGreekMobileInput, sanitizeGreekMobileInput } from "./phone";

describe("sanitizeGreekMobileInput", () => {
  it.each([
    ["\uFF0B\uFF13\uFF10 \uFF16\uFF19\uFF11 \uFF12\uFF13\uFF14 \uFF15\uFF16\uFF17\uFF18", "+30 691 234 5678"],
    ["+\u0663\u0660 \u0666\u0669\u0661 \u0662\u0663\u0664 \u0665\u0666\u0667\u0668", "+30 691 234 5678"],
    ["+\u06F3\u06F0 \u06F6\u06F9\u06F1 \u06F2\u06F3\u06F4 \u06F5\u06F6\u06F7\u06F8", "+30 691 234 5678"],
    ["\u200E+30\u20666912345678\u2069", "+306912345678"],
    ["+30\u200B691\u2060234\u200F5678", "+306912345678"],
    ["+30 691\u2013234\u22125678", "+30 691-234-5678"],
  ])("normalizes OEM phone input %s", (input, expected) => {
    expect(sanitizeGreekMobileInput(input)).toBe(expected);
  });
});

describe("normalizeGreekMobileInput", () => {
  it.each([
    ["+306912345678", "+306912345678"],
    ["+30 691 234 5678", "+306912345678"],
    ["00306912345678", "+306912345678"],
    ["306912345678", "+306912345678"],
    ["6912345678", "+306912345678"],
    ["06912345678", "+306912345678"],
    ["\uFF0B\uFF13\uFF10 \uFF16\uFF19\uFF11 \uFF12\uFF13\uFF14 \uFF15\uFF16\uFF17\uFF18", "+306912345678"],
    ["+\u0663\u0660 \u0666\u0669\u0661 \u0662\u0663\u0664 \u0665\u0666\u0667\u0668", "+306912345678"],
    ["+\u06F3\u06F0 \u06F6\u06F9\u06F1 \u06F2\u06F3\u06F4 \u06F5\u06F6\u06F7\u06F8", "+306912345678"],
    ["\u200E+30\u20666912345678\u2069", "+306912345678"],
    ["+30 691\u2013234\u22125678", "+306912345678"],
  ])("normalizes %s", (input, expected) => {
    expect(normalizeGreekMobileInput(input)).toBe(expected);
  });

  it("preserves the Play reviewer demo number", () => {
    expect(normalizeGreekMobileInput("+306900000000")).toBe("+306900000000");
  });

  it.each([
    "+30+306912345678",
    "+30306912345678",
    "+3000306912345678",
    "+3006912345678",
  ])("repairs a full number pasted after the prefilled prefix: %s", (input) => {
    expect(normalizeGreekMobileInput(input)).toBe("+306912345678");
  });

  it.each([
    "",
    "+30",
    "+30691234567",
    "+3069123456789",
    "+302101234567",
    "+446912345678",
    "+3069ABC45678",
    "+30+30+306912345678",
  ])("rejects invalid or non-Greek mobile input: %s", (input) => {
    expect(normalizeGreekMobileInput(input)).toBeNull();
  });
});
