import { expect, vi } from "vitest";
import { KEYSTORE_LOCK } from "../keystore";

/** FIFO Web Locks stand-in, including shared grants and pending cancellation. */
export function memoryLocks() {
  const pending: Array<{ mode: "shared" | "exclusive"; grant: () => void }> = [];
  let held = 0;
  let exclusive = false;
  const requested = vi.fn();

  function drain() {
    if (exclusive) return;
    while (pending.length) {
      if (pending[0].mode === "exclusive" && held > 0) return;
      pending.shift()!.grant();
      if (exclusive) return;
    }
  }

  return {
    requested,
    request<T>(name: string, options: { mode: "shared" | "exclusive"; signal?: AbortSignal }, cb: () => Promise<T>): Promise<T> {
      expect(name).toBe(KEYSTORE_LOCK);
      requested(name, options);
      return new Promise<T>((resolve, reject) => {
        const { signal } = options;
        if (signal?.aborted) { reject(signal.reason); return; }
        const release = () => { held--; exclusive = false; drain(); };
        const entry = {
          mode: options.mode,
          grant() {
            signal?.removeEventListener("abort", cancel);
            held++;
            exclusive = options.mode === "exclusive";
            Promise.resolve().then(cb).then(
              (value) => { release(); resolve(value); },
              (error) => { release(); reject(error); },
            );
          },
        };
        const cancel = () => {
          pending.splice(pending.indexOf(entry), 1);
          reject(signal!.reason);
          drain();
        };
        signal?.addEventListener("abort", cancel, { once: true });
        pending.push(entry);
        drain();
      });
    },
  };
}
