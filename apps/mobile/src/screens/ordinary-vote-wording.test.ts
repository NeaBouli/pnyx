import { readFileSync } from "node:fs";
import { URL } from "node:url";
import { describe, expect, it } from "vitest";

describe("ordinary participation wording", () => {
  it.each([
    "OnboardingScreen.tsx",
    "VerifyScreen.tsx",
    "MPScreen.tsx",
    "BillsScreen.tsx",
    "VoteScreen.tsx",
    "ProfileScreen.tsx",
  ])("does not promise anonymous participation in %s", (filename) => {
    const source = readFileSync(new URL(filename, import.meta.url), "utf8");

    // ZK-only files are excluded; mixed screens retain their ZK adjectives.
    expect(source).not.toMatch(/ανώνυμα|anonymously/i);
  });
});
