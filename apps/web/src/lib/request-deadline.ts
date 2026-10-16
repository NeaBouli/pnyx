export const REQUEST_TIMEOUT_MS = 15_000;

export class RequestTimeoutError extends Error {
  constructor() {
    super("Request timed out");
    this.name = "TimeoutError";
  }
}

export function requestTimeoutMessage(isEl: boolean): string {
  return isEl
    ? "Το αίτημα καθυστέρησε. Δοκιμάστε ξανά."
    : "The request timed out. Please try again.";
}

/**
 * Keep body consumption inside the deadline, even when fetch ignores abort.
 * Check the signal before later requests so expired work cannot submit again.
 */
export async function withRequestDeadline<T>(
  request: (signal: AbortSignal) => Promise<T>,
  { timeoutMs = REQUEST_TIMEOUT_MS, signal }: { timeoutMs?: number; signal?: AbortSignal } = {},
): Promise<T> {
  signal?.throwIfAborted();
  const controller = new AbortController();
  const forwardAbort = () => controller.abort(signal?.reason);
  signal?.addEventListener("abort", forwardAbort, { once: true });
  let rejectOnAbort!: () => void;
  const deadline = new Promise<never>((_, reject) => {
    rejectOnAbort = () => reject(controller.signal.reason);
    controller.signal.addEventListener("abort", rejectOnAbort, { once: true });
  });
  const timer = setTimeout(() => controller.abort(new RequestTimeoutError()), timeoutMs);
  try {
    return await Promise.race([request(controller.signal), deadline]);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", forwardAbort);
    controller.signal.removeEventListener("abort", rejectOnAbort);
  }
}
