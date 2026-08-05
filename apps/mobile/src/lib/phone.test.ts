import { describe, expect, it } from "vitest";
import { normalizeGreekMobileInput } from "./phone";

describe("normalizeGreekMobileInput", () => {
  it.each([
    ["+306912345678", "+306912345678"],
    ["+30 691 234 5678", "+306912345678"],
    ["00306912345678", "+306912345678"],
    ["306912345678", "+306912345678"],
    ["6912345678", "+306912345678"],
    ["06912345678", "+306912345678"],
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
