import { describe, expect, it } from "vitest";
import { formatZkPilotErrorMessage } from "./zkPilotError";

describe("formatZkPilotErrorMessage", () => {
  it("maps the duplicate scope backend error to a clear Greek message", () => {
    expect(formatZkPilotErrorMessage(new Error("ZK vote already exists for this scope"))).toBe(
      "Έχετε ήδη υποβάλει ανώνυμη ψήφο για αυτό το θέμα."
    );
  });

  it("accepts the duplicate error in mixed casing", () => {
    expect(formatZkPilotErrorMessage("ERROR: zk vote already exists for this scope (bill-001)")).toBe(
      "Έχετε ήδη υποβάλει ανώνυμη ψήφο για αυτό το θέμα."
    );
  });

  it("accepts backend detail payloads", () => {
    expect(formatZkPilotErrorMessage({ detail: "ZK vote already exists for this scope" })).toBe(
      "Έχετε ήδη υποβάλει ανώνυμη ψήφο για αυτό το θέμα."
    );
  });

  it("returns a friendly Greek message for unknown errors by default", () => {
    expect(formatZkPilotErrorMessage("weird backend payload")).toBe(
      "Η ανώνυμη ZK ψήφος δεν υποβλήθηκε. Δοκιμάστε ξανά σε λίγο."
    );
  });

  it("returns context-aware fallback messages", () => {
    expect(formatZkPilotErrorMessage(new Error("timeout"), "verify")).toBe(
      "Η επαλήθευση απέτυχε. Δοκιμάστε ξανά σε λίγο."
    );
    expect(formatZkPilotErrorMessage({}, "optIn")).toBe(
      "Το ZK opt-in δεν ολοκληρώθηκε. Δοκιμάστε ξανά σε λίγο."
    );
  });
});
