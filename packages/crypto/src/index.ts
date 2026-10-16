/**
 * @file index.ts
 * @description Public API for @ekklesia/crypto package.
 */

// Types
export * from "./types.js";

// Voting (Tier 1)
// ADR-006 D1: the phone-derived root functions (deriveNullifierRoot,
// persistNullifierRoot, buildRegistrationPayload) are deliberately NOT part of
// the public API any more; they remain in ./nullifier.ts for the KAT vectors.
export {
  loadNullifierRoot,
  isRegistered,
  deriveIdentityCommitment,
  deriveVoteNullifier,
  deriveLinkageTag,
  deriveEphemeralKeypair,
  buildVotePayload,
  verifyReceipt,
  storeReceipt,
  loadReceipt,
  clearIdentity,
} from "./nullifier.js";

// POLIS Tickets
export {
  derivePolisKeypair,
  deriveTicketNullifier,
  deriveTicketVoteNullifier,
  buildPolisTicketPayload,
  buildPolisVotePayload,
  hashContent,
  getPolisHandle,
  getPolisShortHandle,
} from "./polis.js";
