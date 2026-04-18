/**
 * @file types.ts
 * @description Shared types for ekklesia crypto layer (Tier 1 & POLIS).
 * @module @ekklesia/crypto
 */

// ─── Constants ────────────────────────────────────────────────────────────────

/** Protocol version — bump on breaking changes. */
export const PROTO_VERSION = "ekklesia:v1" as const;

/** Argon2id parameters — chosen for ~500ms on mid-range device (2025). */
export const ARGON2_PARAMS = {
  time:    3,
  memory:  65536,   // 64 MiB
  parallelism: 1,
  hashLen: 32,
  outputType: "binary",
} as const;

/**
 * Public registration salt — not secret.
 * Security comes from Argon2id cost, not salt secrecy.
 * Published openly; changing this invalidates all existing registrations.
 */
export const REGISTRATION_SALT = "ekklesia.gr:registration:2026:v1";

// ─── Domain Separators ────────────────────────────────────────────────────────
// Distinct strings prevent cross-context key reuse.

export const DOMAIN = {
  IDENTITY_COMMITMENT: "ekklesia:identity_commitment:v1",
  VOTE_NULLIFIER:      "ekklesia:vote_nullifier:v1",
  EPHEMERAL_SEED:      "ekklesia:ephemeral_seed:v1",
  LINKAGE_TAG:         "ekklesia:linkage_tag:v1",
  POLIS_KEY:           "ekklesia:polis_key:v1",
  POLIS_NULLIFIER:     "ekklesia:polis_nullifier:v1",
  POLIS_TICKET_KEY:    "ekklesia:polis_ticket_key:v1",
} as const;

// ─── Vote Types ───────────────────────────────────────────────────────────────

export type VoteChoice = "YES" | "NO" | "ABSTAIN";
export type PhoneRegion = "GR" | "CY" | string;
export type TicketCategory = "bug" | "proposal" | "vote";
export type TicketVote = "up" | "down";

// ─── Registration ─────────────────────────────────────────────────────────────

/** Sent to server on first registration. Contains no key material. */
export interface RegistrationPayload {
  /** HMAC-SHA256(nullifier_root, DOMAIN.IDENTITY_COMMITMENT) — hex */
  identity_commitment: string;
  /** ISO 3166-1 alpha-2 phone region */
  phone_region: PhoneRegion;
  /** Protocol version */
  version: typeof PROTO_VERSION;
}

// ─── Voting ───────────────────────────────────────────────────────────────────

/** Signed voting payload sent to server. No key material. */
export interface VotePayload {
  /** Bill identifier e.g. "GR-2026-0042" */
  bill_id: string;
  /** Vote choice */
  choice: VoteChoice;
  /** Ephemeral Ed25519 public key — hex, unique per (user × bill) */
  pk_eph: string;
  /** HMAC-SHA256(nullifier_root, DOMAIN.VOTE_NULLIFIER + ":" + bill_id) — hex */
  vote_nullifier: string;
  /**
   * HMAC-SHA256(HMAC-SHA256(nullifier_root, DOMAIN.LINKAGE_TAG), bill_id) — hex
   * Proves vote_nullifier and identity_commitment share the same nullifier_root
   * without revealing it. (Trust-based in Tier 1; ZK-proven in Tier 2.)
   */
  linkage_tag: string;
  /** Ed25519 signature over canonical payload bytes — hex */
  signature: string;
  /** Unix timestamp ms — server rejects if |now - ts| > 300_000 (5 min) */
  timestamp_ms: number;
  /** Protocol version */
  version: typeof PROTO_VERSION;
}

// ─── POLIS Tickets ────────────────────────────────────────────────────────────

/** Create a new ticket. */
export interface PolisTicketPayload {
  /** Ticket content (max 2000 chars) */
  content: string;
  category: TicketCategory;
  /** Persistent POLIS public key — hex. Consistent across tickets for reputation. */
  pk_polis: string;
  /**
   * HMAC-SHA256(polis_key, DOMAIN.POLIS_NULLIFIER + ":ticket:" + content_hash)
   * Prevents duplicate tickets from same identity.
   */
  ticket_nullifier: string;
  /** Ed25519 signature — hex */
  signature: string;
  timestamp_ms: number;
  version: typeof PROTO_VERSION;
}

/** Vote on an existing ticket (up/down for proposal threshold). */
export interface PolisVotePayload {
  /** Ticket identifier assigned by server */
  ticket_id: string;
  vote: TicketVote;
  /** Same persistent pk_polis — enables reputation / vote-weight */
  pk_polis: string;
  /**
   * HMAC-SHA256(polis_key, DOMAIN.POLIS_NULLIFIER + ":vote:" + ticket_id)
   * Prevents double-voting on same ticket.
   */
  vote_nullifier: string;
  /** Ed25519 signature — hex */
  signature: string;
  timestamp_ms: number;
  version: typeof PROTO_VERSION;
}

// ─── Server Responses ─────────────────────────────────────────────────────────

export interface RegistrationResponse {
  ok: boolean;
  /** Server-assigned identity token (opaque, non-sensitive) */
  identity_token: string;
}

export interface VoteResponse {
  ok: boolean;
  /** Signed receipt — store locally for auditability */
  receipt: VoteReceipt;
}

/**
 * Vote receipt — client stores this.
 * Proves server acknowledged the vote at a specific time.
 * Auditable against Arweave aggregate once bill closes.
 */
export interface VoteReceipt {
  bill_id: string;
  vote_nullifier: string;
  server_timestamp_ms: number;
  /** Server Ed25519 signature over receipt fields — hex */
  server_signature: string;
  /** Server public key for signature verification — hex */
  server_pk: string;
}

export interface PolisTicketResponse {
  ok: boolean;
  ticket_id: string;
}

export interface PolisVoteResponse {
  ok: boolean;
  ticket_id: string;
  current_score: number;
}
