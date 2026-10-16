# Browser key rotation

2026-10-16 — T-9135 review fixes (local only): browser keystore writes request
strict IndexedDB durability and await transaction completion before rotating
the server key. Reused journals are also flushed strictly before mutation.
Engines that reject the options or do not report `transaction.durability ===
"strict"` retain the legacy key/journal and return a retryable result; they do
not start an unsafe rotation. No relaxed-durability fallback is used.

Pending swaps are verified and promoted before reading feature flags or the
version endpoint. If key-check returns 404, recovery uses a signed vote-status
read for a discovered public bill and requires the signed-integrity response
header. Missing bills/endpoints or unreadable storage remain retryable, with
automatic exponential backoff from one minute to fifteen minutes.

SSO, vote status plus vote submission, and relevance signing acquire their
signer inside a shared `ekklesia-keystore` Web Lock and hold it until submission
finishes. Migration, rotation, and Compass writes retain exclusive locks.
There are no browser evaluation signing consumers in this worktree; future
signing consumers must use `withSigner` across the entire request.

Once a key is found, `navigator.storage.persist()` is requested once per page,
best effort. Only `granted`, `denied`, `unsupported`, or `error` is recorded in
`ekklesia_storage_persistence`; no key material is recorded.

Open item: persistent storage is not guaranteed. Eviction, browser data removal,
and device loss still require a separately designed recovery/export UX. This
change does not add that UX.

Validation: `npx --no-install tsc --noEmit` passed; 154 tests passed across 11
focused Vitest suites (keystore, rotation, voting, SSO, relevance, migration,
and Compass). The installed Node 22.11 needs
`NODE_OPTIONS=--experimental-require-module` for the existing jsdom dependency.
No network, installation, push, or deployment is performed.
