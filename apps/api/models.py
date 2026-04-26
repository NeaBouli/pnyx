"""
Ekklesia.gr — Vollständiges Datenbankschema v7
Alle Tabellen: Identity, VAA, Parliament, Voting, Analytics
"""
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, SmallInteger, Boolean,
    DateTime, JSON, ForeignKey, UniqueConstraint, Index,
    CheckConstraint, Enum, Numeric
)
from sqlalchemy.dialects.postgresql import JSONB
from database import Base


# ─── Enums ────────────────────────────────────────────────────────────────────

class BillStatus(str, PyEnum):
    ANNOUNCED        = "ANNOUNCED"
    ACTIVE           = "ACTIVE"
    WINDOW_24H       = "WINDOW_24H"
    PARLIAMENT_VOTED = "PARLIAMENT_VOTED"
    OPEN_END         = "OPEN_END"

class VoteChoice(str, PyEnum):
    YES     = "YES"      # Υπέρ
    NO      = "NO"       # Κατά
    ABSTAIN = "ABSTAIN"  # Αποχή
    UNKNOWN = "UNKNOWN"  # Δεν γνωρίζω

class KeyStatus(str, PyEnum):
    ACTIVE  = "ACTIVE"
    REVOKED = "REVOKED"

class GovernanceLevel(str, PyEnum):
    NATIONAL   = "NATIONAL"
    REGIONAL   = "REGIONAL"
    MUNICIPAL  = "MUNICIPAL"
    COMMUNITY  = "COMMUNITY"


# ─── MOD-01: Identity ─────────────────────────────────────────────────────────

class IdentityRecord(Base):
    """
    Verifizierer Bürger. Kein Personenbezug — nur kryptographische Anker.
    Telefonnummer wird nach Key-Generierung sofort gelöscht (nie gespeichert).
    """
    __tablename__ = "identity_records"

    id              = Column(Integer, primary_key=True)
    nullifier_hash  = Column(String(64), unique=True, nullable=False, index=True)
    public_key_hex  = Column(String(128), nullable=False)
    demographic_hash= Column(String(64), nullable=True)   # SHA256(region+gender+salt)
    age_group       = Column(String(20), nullable=True)   # AGE_18_25 .. AGE_65_PLUS
    region          = Column(String(30), nullable=True)   # REG_ATTICA etc. (legacy)
    gender_code     = Column(String(20), nullable=True)   # GENDER_MALE etc.
    periferia_id    = Column(Integer, ForeignKey("periferia.id", ondelete="SET NULL"), nullable=True)
    dimos_id        = Column(Integer, ForeignKey("dimos.id", ondelete="SET NULL"), nullable=True)
    status          = Column(Enum(KeyStatus), default=KeyStatus.ACTIVE, nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at      = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_identity_nullifier", "nullifier_hash"),
        Index("idx_identity_status", "status"),
    )


# ─── MOD-02: VAA ──────────────────────────────────────────────────────────────

class Party(Base):
    """Griechische Parteien (6-8 im MVP)"""
    __tablename__ = "parties"

    id              = Column(Integer, primary_key=True)
    name_el         = Column(String(100), nullable=False)
    name_en         = Column(String(100), nullable=True)
    abbreviation    = Column(String(20), nullable=True)
    logo_url        = Column(Text, nullable=True)
    color_hex       = Column(String(7), nullable=True)   # #FF0000
    description_el  = Column(Text, nullable=True)
    description_en  = Column(Text, nullable=True)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)


class Statement(Base):
    """VAA-Thesen (15-20 Stück)"""
    __tablename__ = "statements"

    id              = Column(Integer, primary_key=True)
    text_el         = Column(Text, nullable=False)
    text_en         = Column(Text, nullable=True)
    explanation_el  = Column(Text, nullable=True)
    explanation_en  = Column(Text, nullable=True)
    category        = Column(String(50), nullable=True)  # Οικονομία, Περιβάλλον...
    display_order   = Column(Integer, default=0)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)


class PartyPosition(Base):
    """Parteiposition zu einer These: +1 dafür, 0 neutral, -1 dagegen"""
    __tablename__ = "party_positions"

    party_id        = Column(Integer, ForeignKey("parties.id", ondelete="CASCADE"), primary_key=True)
    statement_id    = Column(Integer, ForeignKey("statements.id", ondelete="CASCADE"), primary_key=True)
    position        = Column(SmallInteger, nullable=False)  # -1, 0, 1

    __table_args__ = (
        CheckConstraint("position IN (-1, 0, 1)", name="ck_position_valid"),
    )


# ─── MOD-03: Parliament ───────────────────────────────────────────────────────

class ParliamentBill(Base):
    """
    Parlamentsbeschlüsse — importiert via offizielle API + KI-Scraper (MOD-10/11).
    Lifecycle: ANNOUNCED → ACTIVE → WINDOW_24H → PARLIAMENT_VOTED → OPEN_END
    """
    __tablename__ = "parliament_bills"

    id                  = Column(String(50), primary_key=True)   # z.B. GR-2024-0042
    title_el            = Column(Text, nullable=False)
    title_en            = Column(Text, nullable=True)

    # KI-generierte Zusammenfassungen (MOD-11) — 3 Ebenen
    pill_el             = Column(String(200), nullable=True)     # 1 Satz, max 15 Wörter
    pill_en             = Column(String(200), nullable=True)
    summary_short_el    = Column(Text, nullable=True)            # 3 Absätze
    summary_short_en    = Column(Text, nullable=True)
    summary_long_el     = Column(Text, nullable=True)            # Vollanalyse
    summary_long_en     = Column(Text, nullable=True)

    categories          = Column(JSONB, nullable=True)           # ["Περιβάλλον", ...]
    party_votes_parliament = Column(JSONB, nullable=True)        # {"ΝΔ": "ΝΑΙ", ...}

    status              = Column(Enum(BillStatus), default=BillStatus.ANNOUNCED, nullable=False)
    parliament_vote_date= Column(DateTime, nullable=True)
    status_changed_at   = Column(DateTime, nullable=True)
    parliament_url      = Column(String(500), nullable=True)      # Official hellenicparliament.gr link
    arweave_tx_id       = Column(String(100), nullable=True)     # MOD-08
    ai_summary_reviewed = Column(Boolean, default=False)        # Community-geprüft

    # Vote Scope: who can vote on this bill
    governance_level    = Column(Enum(GovernanceLevel), default=GovernanceLevel.NATIONAL, nullable=False)
    periferia_id        = Column(Integer, ForeignKey("periferia.id", ondelete="SET NULL"), nullable=True)
    dimos_id            = Column(Integer, ForeignKey("dimos.id", ondelete="SET NULL"), nullable=True)

    created_at          = Column(DateTime, default=datetime.utcnow)
    updated_at          = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_bills_status", "status"),
        Index("idx_bills_vote_date", "parliament_vote_date"),
        Index("idx_bills_governance", "governance_level"),
    )


class BillStatusLog(Base):
    """Audit-Log aller Lifecycle-Übergänge"""
    __tablename__ = "bill_status_logs"

    id          = Column(Integer, primary_key=True)
    bill_id     = Column(String(50), ForeignKey("parliament_bills.id"), nullable=False)
    from_status = Column(String(30), nullable=True)
    to_status   = Column(String(30), nullable=False)
    changed_at  = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_statuslog_bill", "bill_id"),
    )


# ─── MOD-04: CitizenVote ──────────────────────────────────────────────────────

class CitizenVote(Base):
    """
    Bürger-Abstimmung zu Parlamentsbeschlüssen.
    Kein Personenbezug: nur Nullifier Hash + Ed25519-Signatur.
    UNIQUE(nullifier_hash, bill_id) verhindert Doppelstimme auf DB-Ebene.
    """
    __tablename__ = "citizen_votes"

    id              = Column(Integer, primary_key=True)
    nullifier_hash  = Column(String(64), nullable=False)
    bill_id         = Column(String(50), ForeignKey("parliament_bills.id"), nullable=False)
    vote            = Column(Enum(VoteChoice), nullable=False)
    signature_hex   = Column(String(128), nullable=False)   # Ed25519 Signatur
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("nullifier_hash", "bill_id", name="uq_one_vote_per_citizen"),
        Index("idx_votes_bill", "bill_id"),
        Index("idx_votes_nullifier", "nullifier_hash"),
    )


class BillRelevanceVote(Base):
    """
    Up/Down Relevanz-Signal (MOD-14): Bürger entscheiden was wichtig ist.
    Getrennt von der inhaltlichen Stimme (CitizenVote).
    """
    __tablename__ = "bill_relevance_votes"

    nullifier_hash  = Column(String(64), primary_key=True)
    bill_id         = Column(String(50), ForeignKey("parliament_bills.id"), primary_key=True)
    signal          = Column(SmallInteger, nullable=False)  # +1 relevant, -1 nicht relevant
    created_at      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("signal IN (1, -1)", name="ck_relevance_signal"),
    )


# ─── MOD-02: VAA Survey Responses ────────────────────────────────────────────

class SurveyResponse(Base):
    """
    VAA-Antworten eines Bürgers.
    demographic_hash: SHA256(age_group + region + gender + SERVER_SALT)
    Kein Rückschluss auf reale Identität möglich.
    """
    __tablename__ = "survey_responses"

    id              = Column(Integer, primary_key=True)
    user_hash       = Column(String(64), nullable=False)
    age_group       = Column(String(20), nullable=True)
    region          = Column(String(30), nullable=True)
    gender_code     = Column(String(20), nullable=True)
    answers         = Column(JSONB, nullable=False)      # {statement_id: -1|0|1}
    created_at      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_survey_hash", "user_hash"),
        Index("idx_survey_demographics", "age_group", "region"),
    )


# ─── MOD-16: Municipal Governance ────────────────────────────────────────────


class Periferia(Base):
    """Περιφέρειες Ελλάδας (13 + Άγιο Όρος)"""
    __tablename__ = "periferia"

    id         = Column(Integer, primary_key=True)
    name_el    = Column(String(100), nullable=False)
    name_en    = Column(String(100), nullable=True)
    code       = Column(String(10), unique=True, nullable=False)   # e.g. GR-ATT
    is_active  = Column(Boolean, default=True)

    __table_args__ = (
        Index("idx_periferia_code", "code"),
    )


class Dimos(Base):
    """Δήμοι Ελλάδας (~332)"""
    __tablename__ = "dimos"

    id            = Column(Integer, primary_key=True)
    name_el       = Column(String(100), nullable=False)
    name_en       = Column(String(100), nullable=True)
    periferia_id  = Column(Integer, ForeignKey("periferia.id", ondelete="CASCADE"), nullable=False)
    population    = Column(Integer, nullable=True)
    is_active     = Column(Boolean, default=True)

    __table_args__ = (
        Index("idx_dimos_periferia", "periferia_id"),
    )


class Community(Base):
    """Κοινότητες / Δημοτικές Ενότητες"""
    __tablename__ = "communities"

    id         = Column(Integer, primary_key=True)
    name_el    = Column(String(100), nullable=False)
    name_en    = Column(String(100), nullable=True)
    dimos_id   = Column(Integer, ForeignKey("dimos.id", ondelete="CASCADE"), nullable=False)
    is_active  = Column(Boolean, default=True)

    __table_args__ = (
        Index("idx_community_dimos", "dimos_id"),
    )


class Decision(Base):
    """
    Αποφάσεις σε όλα τα επίπεδα διακυβέρνησης (MOD-16).
    Αντίστοιχο του ParliamentBill αλλά για τοπική αυτοδιοίκηση.
    """
    __tablename__ = "decisions"

    id                = Column(Integer, primary_key=True)
    title_el          = Column(Text, nullable=False)
    title_en          = Column(Text, nullable=True)
    pill_el           = Column(String(200), nullable=True)      # 1 Satz, max 15 Wörter
    pill_en           = Column(String(200), nullable=True)
    summary_short_el  = Column(Text, nullable=True)             # 3 Absätze
    summary_short_en  = Column(Text, nullable=True)

    level             = Column(Enum(GovernanceLevel), nullable=False, default=GovernanceLevel.MUNICIPAL)
    periferia_id      = Column(Integer, ForeignKey("periferia.id"), nullable=True)
    dimos_id          = Column(Integer, ForeignKey("dimos.id"), nullable=True)
    community_id      = Column(Integer, ForeignKey("communities.id"), nullable=True)

    categories        = Column(JSONB, nullable=True)            # ["Περιβάλλον", ...]
    authority_votes   = Column(JSONB, nullable=True)            # {"ΝΑΙ": 15, "ΟΧΙ": 8}
    status            = Column(Enum(BillStatus), default=BillStatus.ANNOUNCED, nullable=False)
    vote_date         = Column(DateTime, nullable=True)
    diavgeia_ada      = Column(String(32), ForeignKey("diavgeia_decisions.ada", ondelete="SET NULL"), nullable=True)

    created_at        = Column(DateTime, default=datetime.utcnow)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_decisions_level", "level"),
        Index("idx_decisions_status", "status"),
        Index("idx_decisions_periferia", "periferia_id"),
        Index("idx_decisions_dimos", "dimos_id"),
        Index("idx_decisions_vote_date", "vote_date"),
        Index("ix_decisions_diavgeia_ada", "diavgeia_ada"),
    )


# ─── MOD-21: Diavgeia Integration ─────────────────────────────────────────

class DiavgeiaDecision(Base):
    """
    Raw Diavgeia decisions (government transparency portal).
    Separate from curated `decisions` table — raw layer for high-volume data.
    """
    __tablename__ = "diavgeia_decisions"

    id                    = Column(BigInteger, primary_key=True, autoincrement=True)
    ada                   = Column(String(32), unique=True, nullable=False)
    subject               = Column(Text, nullable=False)
    decision_type_uid     = Column(String(16), nullable=False)
    decision_type_label   = Column(Text)
    organization_uid      = Column(String(16), nullable=False)
    organization_label    = Column(Text, nullable=False)
    document_url          = Column(Text, nullable=False)
    submission_timestamp  = Column(DateTime(timezone=True))
    publish_timestamp     = Column(DateTime(timezone=True), nullable=False)
    raw_payload           = Column(JSONB, nullable=False)
    fetched_at            = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    dimos_id              = Column(Integer, ForeignKey("dimos.id", ondelete="SET NULL"), nullable=True)
    periferia_id          = Column(Integer, ForeignKey("periferia.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint("length(ada) BETWEEN 10 AND 32", name="diavgeia_decisions_ada_chk"),
        Index("ix_diavgeia_decisions_org_published", "organization_uid", publish_timestamp.desc()),
        Index("ix_diavgeia_decisions_dimos_published", "dimos_id", publish_timestamp.desc()),
        Index("ix_diavgeia_decisions_type_published", "decision_type_uid", publish_timestamp.desc()),
    )

    def __repr__(self) -> str:
        return f"<DiavgeiaDecision ada={self.ada} org={self.organization_uid}>"


class DimosDiavgeiaOrg(Base):
    """Mapping between ekklesia dimos and Diavgeia organization UIDs (1:N)."""
    __tablename__ = "dimos_diavgeia_orgs"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    dimos_id         = Column(Integer, ForeignKey("dimos.id", ondelete="CASCADE"), nullable=False)
    diavgeia_uid     = Column(String(16), nullable=False)
    org_label        = Column(Text, nullable=False)
    org_category     = Column(String(32))
    is_primary       = Column(Boolean, nullable=False, default=False)
    match_confidence = Column(Numeric(4, 3))
    verified_at      = Column(DateTime(timezone=True))
    created_at       = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("dimos_id", "diavgeia_uid", name="uq_dimos_diavgeia_org"),
        Index("ix_dimos_diavgeia_orgs_uid", "diavgeia_uid"),
    )

    def __repr__(self) -> str:
        return f"<DimosDiavgeiaOrg dimos={self.dimos_id} uid={self.diavgeia_uid}>"
