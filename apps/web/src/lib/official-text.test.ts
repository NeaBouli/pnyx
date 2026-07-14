import { describe, expect, it } from "vitest";
import { cleanOfficialText } from "./official-text";

describe("cleanOfficialText", () => {
  it("removes an upstream access-denial response", () => {
    expect(cleanOfficialText(
      `You don't have permission to access "/" on this server. Reference #18.63c7cf17`,
    )).toBe("");
  });

  it("keeps Parliament PDF links appended after an access denial", () => {
    const value = `
You don't have permission to access "/" on this server. Reference #18.63c7cf17

### Πλήρη έγγραφα
- [Έγγραφο Βουλής](https://www.hellenicparliament.gr/UserFiles/13351763.pdf)
`;

    expect(cleanOfficialText(value)).toBe(
      "### Πλήρη έγγραφα\n- [Έγγραφο Βουλής](https://www.hellenicparliament.gr/UserFiles/13351763.pdf)",
    );
  });

  it("keeps legitimate official text", () => {
    expect(cleanOfficialText("Άρθρο 1\nΣκοπός του νόμου."))
      .toBe("Άρθρο 1\nΣκοπός του νόμου.");
  });

  it("does not reject a legitimate text for the words access denied alone", () => {
    const value = "Η φράση Access Denied αναφέρεται ως τεχνικός όρος στο επίσημο κείμενο.";
    expect(cleanOfficialText(value)).toBe(value);
  });
});
