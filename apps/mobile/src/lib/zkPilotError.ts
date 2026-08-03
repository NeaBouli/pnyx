export type ZkPilotErrorContext = "vote" | "verify" | "optIn";

const KNOWN_DUPLICATE_ERROR = /zk vote already exists for this scope/i;

const UNKNOWN_ERRORS: Record<ZkPilotErrorContext, string> = {
  vote: "Η ανώνυμη ZK ψήφος δεν υποβλήθηκε. Δοκιμάστε ξανά σε λίγο.",
  verify: "Η επαλήθευση απέτυχε. Δοκιμάστε ξανά σε λίγο.",
  optIn: "Το ZK opt-in δεν ολοκληρώθηκε. Δοκιμάστε ξανά σε λίγο.",
};

function normalizeErrorMessage(error: unknown): string {
  if (typeof error === "string") return error.trim();
  if (error instanceof Error && error.message) return error.message.trim();

  if (typeof error === "object" && error !== null) {
    const detailCandidate = (error as { detail?: unknown }).detail;
    if (typeof detailCandidate === "string" && detailCandidate.trim()) return detailCandidate.trim();

    const messageCandidate = (error as { message?: unknown }).message;
    if (typeof messageCandidate === "string" && messageCandidate.trim()) return messageCandidate.trim();
  }

  return "";
}

export function formatZkPilotErrorMessage(
  error: unknown,
  context: ZkPilotErrorContext = "vote",
): string {
  const message = normalizeErrorMessage(error);

  if (KNOWN_DUPLICATE_ERROR.test(message)) {
    return "Έχετε ήδη υποβάλει ανώνυμη ψήφο για αυτό το θέμα.";
  }

  return UNKNOWN_ERRORS[context];
}
