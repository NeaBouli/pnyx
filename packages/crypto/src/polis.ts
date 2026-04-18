/**
 * @file polis.ts
 * @description Client-side POLIS ticket crypto for ekklesia.gr.
 *
 * Protocol summary:
 *   - Persistent Ed25519 keypair derived from nullifier_root (domain-separated).
 *   - Same pk_polis across all tickets → enables reputation / vote-weight.
 *   - ticket_nullifier and vote_nullifier prevent duplicates without identity exposure.
 *   - Ticket content is anonymous: server sees pk_polis but cannot link to phone.
 *   - Domain separation ensures pk_polis ≠ any voting key (no cross-correlation).
 *
 * @module @ekklesia/crypto/polis
 */

import { hmac }           from "@noble/hashes/hmac";
import { sha256 }         from "@noble/hashes/sha256";
import { ed25519 }        from "@noble/curves/ed25519";
import {
  bytesToHex,
  hexToBytes,
  utf8ToBytes,
  concatBytes,
}                          from "@noble/hashes/utils";
import {
  DOMAIN,
  PROTO_VERSION,
  type PolisTicketPayload,
  type PolisVotePayload,
  type TicketCategory,
  type TicketVote,
} from "./types.js";

// ─── Internal helpers ─────────────────────────────────────────────────────────

function hmacSha256(key: Uint8Array, domain: string, suffix?: Uint8Array): Uint8Array {
  const domainBytes = utf8ToBytes(domain);
  const message     = suffix ? concatBytes(domainBytes, suffix) : domainBytes;
  return hmac(sha256, key, message);
}

// ─── POLIS Key Derivation ─────────────────────────────────────────────────────

/**
 * Derives the persistent POLIS keypair from nullifier_root.
 *
 * Domain-separated from all voting keys:
 *   polis_key = HMAC-SHA256(nullifier_root, DOMAIN.POLIS_KEY)
 *   sk_polis  = HMAC-SHA256(polis_key, DOMAIN.POLIS_TICKET_KEY)
 *   pk_polis  = Ed25519.getPublicKey(sk_polis)
 *
 * Properties:
 *   - Deterministic: same nullifier_root → same keypair
 *   - Isolated: cannot be correlated with vote_nullifiers
 *   - Persistent: unlike voting keys, NOT discarded after use (reputation)
 *
 * @param nullifierRoot - 32-byte root secret
 * @returns { sk_polis, pk_polis, polis_key }
 */
export function derivePolisKeypair(nullifierRoot: Uint8Array): {
  sk_polis:   Uint8Array;
  pk_polis:   Uint8Array;
  polis_key:  Uint8Array;
} {
  const polis_key = hmacSha256(nullifierRoot, DOMAIN.POLIS_KEY);
  const sk_polis  = hmacSha256(polis_key, DOMAIN.POLIS_TICKET_KEY);
  const pk_polis  = ed25519.getPublicKey(sk_polis);
  return { sk_polis, pk_polis, polis_key };
}

// ─── Nullifiers ───────────────────────────────────────────────────────────────

/**
 * Derives a ticket_nullifier for a specific content hash.
 * Prevents duplicate tickets from the same identity.
 *
 * @param polisKey    - Intermediate key (from derivePolisKeypair)
 * @param contentHash - SHA256 of ticket content (hex) — not the content itself
 * @returns ticket_nullifier as hex string
 */
export function deriveTicketNullifier(polisKey: Uint8Array, contentHash: string): string {
  const nullifier = hmacSha256(
    polisKey,
    DOMAIN.POLIS_NULLIFIER + ":ticket:" + contentHash,
  );
  return bytesToHex(nullifier);
}

/**
 * Derives a vote_nullifier for a specific ticket_id.
 * Prevents double-voting on the same ticket.
 *
 * @param polisKey - Intermediate key (from derivePolisKeypair)
 * @param ticketId - Server-assigned ticket identifier
 * @returns vote_nullifier as hex string
 */
export function deriveTicketVoteNullifier(polisKey: Uint8Array, ticketId: string): string {
  const nullifier = hmacSha256(
    polisKey,
    DOMAIN.POLIS_NULLIFIER + ":vote:" + ticketId,
  );
  return bytesToHex(nullifier);
}

// ─── Payload Builders ─────────────────────────────────────────────────────────

/**
 * Hashes ticket content to a hex string.
 * Used for nullifier derivation — server never needs the preimage.
 */
export function hashContent(content: string): string {
  return bytesToHex(sha256(utf8ToBytes(content)));
}

/**
 * Builds the canonical bytes for a ticket creation signature.
 *
 * Layout: version(1B) | category_len(1B) | category | content_hash(32B) | timestamp(8B)
 */
function buildTicketSignedBytes(
  category:    TicketCategory,
  contentHash: string,
  pkPolis:     Uint8Array,
  nullifier:   Uint8Array,
  timestampMs: number,
): Uint8Array {
  const versionByte  = new Uint8Array([1]);
  const catBytes     = utf8ToBytes(category);
  const catLenByte   = new Uint8Array([catBytes.length]);
  const chBytes      = hexToBytes(contentHash);

  const tsBuf = new ArrayBuffer(8);
  new DataView(tsBuf).setBigUint64(0, BigInt(timestampMs), false);
  const tsBytes = new Uint8Array(tsBuf);

  return concatBytes(
    versionByte, catLenByte, catBytes,
    chBytes, pkPolis, nullifier, tsBytes,
  );
}

/**
 * Builds the canonical bytes for a ticket vote signature.
 *
 * Layout: version(1B) | ticket_id_len(2B) | ticket_id | vote(1B) |
 *         pk_polis(32B) | vote_nullifier(32B) | timestamp(8B)
 */
function buildVoteSignedBytes(
  ticketId:    string,
  vote:        TicketVote,
  pkPolis:     Uint8Array,
  nullifier:   Uint8Array,
  timestampMs: number,
): Uint8Array {
  const versionByte     = new Uint8Array([1]);
  const ticketBytes     = utf8ToBytes(ticketId);
  const ticketLenBytes  = new Uint8Array(2);
  new DataView(ticketLenBytes.buffer).setUint16(0, ticketBytes.length, false);

  const voteMap: Record<TicketVote, number> = { up: 1, down: 2 };
  const voteByte = new Uint8Array([voteMap[vote]]);

  const tsBuf = new ArrayBuffer(8);
  new DataView(tsBuf).setBigUint64(0, BigInt(timestampMs), false);
  const tsBytes = new Uint8Array(tsBuf);

  return concatBytes(
    versionByte, ticketLenBytes, ticketBytes,
    voteByte, pkPolis, nullifier, tsBytes,
  );
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Builds a signed PolisTicketPayload ready to POST to /api/tickets.
 *
 * @param nullifierRoot - 32-byte root secret (from loadNullifierRoot())
 * @param content       - Ticket content (max 2000 chars, validated server-side)
 * @param category      - Ticket category
 * @returns Signed PolisTicketPayload
 */
export function buildPolisTicketPayload(
  nullifierRoot: Uint8Array,
  content:       string,
  category:      TicketCategory,
): PolisTicketPayload {
  if (content.length > 2000) {
    throw new Error("Ticket content exceeds 2000 character limit");
  }

  const { sk_polis, pk_polis, polis_key } = derivePolisKeypair(nullifierRoot);
  const contentHash    = hashContent(content);
  const ticketNullifier = deriveTicketNullifier(polis_key, contentHash);
  const timestampMs     = Date.now();

  const signedBytes = buildTicketSignedBytes(
    category,
    contentHash,
    pk_polis,
    hexToBytes(ticketNullifier),
    timestampMs,
  );
  const signature = ed25519.sign(signedBytes, sk_polis);

  return {
    content,
    category,
    pk_polis:         bytesToHex(pk_polis),
    ticket_nullifier: ticketNullifier,
    signature:        bytesToHex(signature),
    timestamp_ms:     timestampMs,
    version:          PROTO_VERSION,
  };
}

/**
 * Builds a signed PolisVotePayload ready to POST to /api/tickets/{id}/vote.
 *
 * @param nullifierRoot - 32-byte root secret
 * @param ticketId      - Server-assigned ticket identifier
 * @param vote          - "up" or "down"
 * @returns Signed PolisVotePayload
 */
export function buildPolisVotePayload(
  nullifierRoot: Uint8Array,
  ticketId:      string,
  vote:          TicketVote,
): PolisVotePayload {
  const { sk_polis, pk_polis, polis_key } = derivePolisKeypair(nullifierRoot);
  const voteNullifier = deriveTicketVoteNullifier(polis_key, ticketId);
  const timestampMs   = Date.now();

  const signedBytes = buildVoteSignedBytes(
    ticketId,
    vote,
    pk_polis,
    hexToBytes(voteNullifier),
    timestampMs,
  );
  const signature = ed25519.sign(signedBytes, sk_polis);

  return {
    ticket_id:      ticketId,
    vote,
    pk_polis:       bytesToHex(pk_polis),
    vote_nullifier: voteNullifier,
    signature:      bytesToHex(signature),
    timestamp_ms:   timestampMs,
    version:        PROTO_VERSION,
  };
}

// ─── Reputation helpers ───────────────────────────────────────────────────────

/**
 * Returns the pk_polis for display / reputation queries.
 * First 8 chars used as display handle (e.g. "a3f7c9b2").
 *
 * @param nullifierRoot - 32-byte root secret
 * @returns pk_polis hex string
 */
export function getPolisHandle(nullifierRoot: Uint8Array): string {
  const { pk_polis } = derivePolisKeypair(nullifierRoot);
  return bytesToHex(pk_polis);
}

/**
 * Short display handle (first 8 hex chars of pk_polis).
 * Used in the ticket board UI.
 */
export function getPolisShortHandle(nullifierRoot: Uint8Array): string {
  return getPolisHandle(nullifierRoot).slice(0, 8);
}
