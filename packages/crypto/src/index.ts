/**
 * @file index.ts
 * @description Public API for @ekklesia/crypto package.
 */

// Types
export * from "./types.js";

// Voting (Tier 1)
export {
  deriveNullifierRoot,
  persistNullifierRoot,
  loadNullifierRoot,
  isRegistered,
  deriveIdentityCommitment,
  buildRegistrationPayload,
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
