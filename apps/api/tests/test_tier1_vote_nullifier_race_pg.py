"""T-410: Tier-1 vote_nullifier atomicity and all-or-nothing vote changes.

Real PostgreSQL only (PNYX_TEST_POSTGRES_URL, loopback, pnyx_test_* database).
Each request runs in its own AsyncSession/connection. A barrier inside
AsyncSession.commit() holds racing requests until all have passed the router's
nullifier pre-check, so the unique index — not the pre-check — decides.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import HTTPException
from nacl.signing import SigningKey
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

# Import the app first, like production (keypair import order, see EKA-10 test).
import main  # noqa: F401
from crypto.nullifier import build_signed_payload
from models import (
    BillStatus,
    CitizenVote,
    GovernanceLevel,
    IdentityRecord,
    KeyStatus,
    ParliamentBill,
    VoteChoice,
)
from routers import voting
from tests.pg_vote_schema import (
    disposable_postgres_url,
    drop_vote_schema,
    requires_postgres,
    reset_vote_schema,
)

pytestmark = requires_postgres

BILL_A = "GR-T410-A"
BILL_B = "GR-T410-B"
BILL_W = "GR-T410-W"  # WINDOW_24H: vote change + one-time correction allowed
NULLIFIER = "ab" * 32
OTHER_NULLIFIER = "cd" * 32


class Citizen:
    def __init__(self, marker: str) -> None:
        self.nullifier_hash = marker * 64
        self.key = SigningKey.generate()

    def identity_signature(self, bill_id: str, vote: str) -> str:
        payload = f"{bill_id}:{vote}:{self.nullifier_hash}".encode()
        return self.key.sign(payload).signature.hex()


def tier1_fields(
    bill_id: str,
    vote: str,
    vote_nullifier: str,
    *,
    linkage_tag: str | None = None,
    timestamp_ms: int | None = None,
) -> dict[str, Any]:
    """Freshly signed Tier-1 payload with a new ephemeral key."""
    eph = SigningKey.generate()
    pk_eph = bytes(eph.verify_key)
    tag = linkage_tag or SigningKey.generate().encode().hex()
    ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    message = build_signed_payload(
        bill_id=bill_id,
        choice=vote,
        pk_eph=pk_eph,
        vote_nullifier=bytes.fromhex(vote_nullifier),
        linkage_tag=bytes.fromhex(tag),
        timestamp_ms=ts,
    )
    return {
        "pk_eph": pk_eph.hex(),
        "vote_nullifier": vote_nullifier,
        "linkage_tag": tag,
        "timestamp_ms": ts,
        "tier1_signature_hex": eph.sign(message).signature.hex(),
    }


def vote_request(
    citizen: Citizen, bill_id: str, vote: str, vote_nullifier: str | None = None, **kw: Any,
) -> voting.VoteRequest:
    tier1 = tier1_fields(bill_id, vote, vote_nullifier, **kw) if vote_nullifier else {}
    return voting.VoteRequest(
        nullifier_hash=citizen.nullifier_hash,
        bill_id=bill_id,
        vote=vote,
        signature_hex=citizen.identity_signature(bill_id, vote),
        **tier1,
    )


def correction_request(
    citizen: Citizen, bill_id: str, vote: str, vote_nullifier: str | None = None, **kw: Any,
) -> voting.CorrectionRequest:
    tier1 = tier1_fields(bill_id, vote, vote_nullifier, **kw) if vote_nullifier else {}
    return voting.CorrectionRequest(
        nullifier_hash=citizen.nullifier_hash,
        bill_id=bill_id,
        vote=vote,
        signature_hex=citizen.identity_signature(bill_id, vote),
        **tier1,
    )


@pytest.fixture(autouse=True)
def _guard_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZK_TIER1_GUARD_ENABLED", raising=False)


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    # Pooled (not NullPool): Docker-on-macOS connects are slow; racing sessions
    # still get distinct connections from the pool.
    eng = create_async_engine(disposable_postgres_url(), pool_size=5, max_overflow=5)
    async with eng.begin() as conn:
        await reset_vote_schema(conn, with_nullifier_index=True)
        for bill_id, bill_status in (
            (BILL_A, BillStatus.ACTIVE),
            (BILL_B, BillStatus.ACTIVE),
            (BILL_W, BillStatus.WINDOW_24H),
        ):
            await conn.execute(insert(ParliamentBill.__table__).values(
                id=bill_id,
                title_el="T-410",
                status=bill_status.name,
                governance_level=GovernanceLevel.NATIONAL.name,
            ))
    try:
        yield eng
    finally:
        async with eng.begin() as conn:
            await drop_vote_schema(conn)
        await eng.dispose()


@pytest.fixture
async def citizens(engine: AsyncEngine) -> list[Citizen]:
    people = [Citizen(marker) for marker in "123"]
    async with engine.begin() as conn:
        for idx, person in enumerate(people, start=1):
            await conn.execute(insert(IdentityRecord.__table__).values(
                id=idx,
                nullifier_hash=person.nullifier_hash,
                nullifier_version="v1",
                public_key_hex=person.key.verify_key.encode().hex(),
                region_locked=False,
                source="SMS",
                status=KeyStatus.ACTIVE.name,
                created_at=func.now(),
            ))
    return people


class _BarrierSession(AsyncSession):
    """Holds commit() until every racing request has passed its pre-check."""

    barrier: asyncio.Barrier

    async def commit(self) -> None:
        await self.barrier.wait()
        await super().commit()


async def _outcome(coro: Any) -> Any:
    try:
        return await coro
    except HTTPException as exc:
        return exc.status_code
    except Exception as exc:  # noqa: BLE001 - the race outcome is the assertion subject
        return exc


async def _holders(engine: AsyncEngine, vote_nullifier: str) -> list[CitizenVote]:
    async with AsyncSession(engine) as db:
        result = await db.execute(
            select(CitizenVote).where(
                func.lower(CitizenVote.vote_nullifier) == vote_nullifier.lower()
            )
        )
        return list(result.scalars())


async def _vote_row(engine: AsyncEngine, citizen: Citizen, bill_id: str) -> dict[str, Any] | None:
    async with engine.connect() as conn:
        row = (await conn.execute(
            select(CitizenVote.__table__).where(
                CitizenVote.nullifier_hash == citizen.nullifier_hash,
                CitizenVote.bill_id == bill_id,
            )
        )).mappings().one_or_none()
    return dict(row) if row else None


async def _submit(engine: AsyncEngine, req: voting.VoteRequest) -> Any:
    async with AsyncSession(engine, expire_on_commit=False) as db:
        return await voting.submit_vote(req, db)


async def _correct(engine: AsyncEngine, bill_id: str, req: voting.CorrectionRequest) -> Any:
    async with AsyncSession(engine, expire_on_commit=False) as db:
        return await voting.correct_vote(bill_id, req, db)


# ── Parallel identities, one nullifier ───────────────────────────────────────

@pytest.mark.parametrize("second_bill", [BILL_A, BILL_B], ids=["same-bill", "other-bill"])
@pytest.mark.parametrize("second_case", ["lower", "upper"])
async def test_parallel_identities_same_nullifier_one_commit_one_409(
    engine: AsyncEngine, citizens: list[Citizen], second_bill: str, second_case: str,
) -> None:
    alice, bob, _ = citizens
    second_nullifier = NULLIFIER.upper() if second_case == "upper" else NULLIFIER
    requests = [
        vote_request(alice, BILL_A, "YES", NULLIFIER),
        vote_request(bob, second_bill, "NO", second_nullifier),
    ]
    _BarrierSession.barrier = asyncio.Barrier(2)
    sessions = [_BarrierSession(engine, expire_on_commit=False) for _ in range(2)]
    try:
        outcomes = await asyncio.wait_for(asyncio.gather(*(
            _outcome(voting.submit_vote(req, db)) for req, db in zip(requests, sessions)
        )), timeout=30)

        successes = [o for o in outcomes if isinstance(o, voting.VoteResponse)]
        assert len(successes) == 1, outcomes
        assert outcomes.count(409) == 1, outcomes

        holders = await _holders(engine, NULLIFIER)
        assert len(holders) == 1
        assert holders[0].vote_nullifier == NULLIFIER  # canonical lowercase
        async with AsyncSession(engine) as db:
            assert await db.scalar(select(func.count()).select_from(CitizenVote)) == 1

        # The losing session was rolled back and is usable again.
        for db in sessions:
            assert await db.scalar(select(func.count()).select_from(CitizenVote)) == 1
    finally:
        for db in sessions:
            await db.close()


async def test_http_parallel_identities_return_200_and_409(
    engine: AsyncEngine, citizens: list[Citizen],
) -> None:
    from httpx import ASGITransport, AsyncClient

    from database import get_db

    alice, bob, _ = citizens
    bodies = [
        vote_request(alice, BILL_A, "YES", NULLIFIER).model_dump(),
        vote_request(bob, BILL_B, "YES", NULLIFIER.upper()).model_dump(),
    ]
    _BarrierSession.barrier = asyncio.Barrier(2)

    async def _racing_db() -> AsyncIterator[AsyncSession]:
        async with _BarrierSession(engine, expire_on_commit=False) as session:
            yield session

    main.app.dependency_overrides[get_db] = _racing_db
    try:
        transport = ASGITransport(app=main.app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            responses = await asyncio.wait_for(asyncio.gather(
                *(client.post("/api/v1/vote", json=body) for body in bodies)
            ), timeout=30)
    finally:
        main.app.dependency_overrides.pop(get_db, None)

    assert sorted(r.status_code for r in responses) == [200, 409]
    conflict = next(r for r in responses if r.status_code == 409)
    assert conflict.json() == {"detail": voting.TIER1_DUPLICATE_DETAIL}
    assert len(await _holders(engine, NULLIFIER)) == 1


async def test_sequential_case_variant_rejected_by_precheck(
    engine: AsyncEngine, citizens: list[Citizen],
) -> None:
    alice, bob, _ = citizens
    await _submit(engine, vote_request(alice, BILL_A, "YES", NULLIFIER.upper()))
    stored = await _vote_row(engine, alice, BILL_A)
    assert stored["vote_nullifier"] == NULLIFIER
    assert stored["pk_eph"] == stored["pk_eph"].lower()

    with pytest.raises(HTTPException) as exc:
        await _submit(engine, vote_request(bob, BILL_B, "YES", NULLIFIER))
    assert exc.value.status_code == 409
    assert len(await _holders(engine, NULLIFIER)) == 1


async def test_insert_race_past_precheck_maps_to_409_and_rolls_back(
    engine: AsyncEngine, citizens: list[Citizen], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A competitor committing after the pre-check still ends as 409, not 500."""
    alice, bob, _ = citizens
    real_precheck = voting._tier1_vote_nullifier_used
    competitor = vote_request(bob, BILL_B, "NO", NULLIFIER.upper())

    async def precheck_then_competitor(db: AsyncSession, **kw: Any) -> bool:
        used = await real_precheck(db, **kw)
        if kw["nullifier_hash"] == alice.nullifier_hash:
            await _submit(engine, competitor)  # commits first, after alice's pre-check
        return used

    monkeypatch.setattr(voting, "_tier1_vote_nullifier_used", precheck_then_competitor)
    async with AsyncSession(engine, expire_on_commit=False) as db:
        with pytest.raises(HTTPException) as exc:
            await voting.submit_vote(vote_request(alice, BILL_A, "YES", NULLIFIER), db)
        assert exc.value.status_code == 409
        assert exc.value.detail == voting.TIER1_DUPLICATE_DETAIL
        assert await db.scalar(select(func.count()).select_from(CitizenVote)) == 1

    (holder,) = await _holders(engine, NULLIFIER)
    assert holder.nullifier_hash == bob.nullifier_hash
    assert await _vote_row(engine, alice, BILL_A) is None


# ── Foreign integrity errors stay unmasked ───────────────────────────────────

@pytest.mark.parametrize("kind", ["unique", "foreign-key", "check"])
async def test_foreign_integrity_errors_are_reraised_after_rollback(
    engine: AsyncEngine, citizens: list[Citizen], kind: str,
) -> None:
    alice, bob, _ = citizens
    tag = "ef" * 32
    await _submit(engine, vote_request(alice, BILL_A, "YES", NULLIFIER, linkage_tag=tag))
    async with engine.begin() as conn:
        if kind == "unique":
            await conn.execute(text(
                "CREATE UNIQUE INDEX uq_test_t410_linkage ON citizen_votes (linkage_tag)"
            ))
        elif kind == "foreign-key":
            await conn.execute(text("CREATE TABLE t410_known_tags (tag varchar(64) PRIMARY KEY)"))
            await conn.execute(text(
                "ALTER TABLE citizen_votes ADD CONSTRAINT fk_test_t410_linkage"
                " FOREIGN KEY (linkage_tag) REFERENCES t410_known_tags (tag) NOT VALID"
            ))
        else:
            await conn.execute(text(
                "ALTER TABLE citizen_votes ADD CONSTRAINT ck_test_t410_linkage"
                f" CHECK (linkage_tag <> '{tag}') NOT VALID"
            ))
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            with pytest.raises(IntegrityError):
                await voting.submit_vote(
                    vote_request(bob, BILL_B, "NO", OTHER_NULLIFIER, linkage_tag=tag), db,
                )
            # Rolled back: the session is usable and nothing leaked in.
            assert await db.scalar(select(func.count()).select_from(CitizenVote)) == 1
        assert await _holders(engine, OTHER_NULLIFIER) == []
    finally:
        if kind == "foreign-key":
            async with engine.begin() as conn:
                await conn.execute(text(
                    "ALTER TABLE citizen_votes DROP CONSTRAINT fk_test_t410_linkage"
                ))
                await conn.execute(text("DROP TABLE t410_known_tags"))


# ── Legacy / Tier-0 rows ─────────────────────────────────────────────────────

async def test_legacy_null_rows_unaffected(engine: AsyncEngine, citizens: list[Citizen]) -> None:
    alice, bob, carol = citizens
    for person in (alice, bob):
        await _submit(engine, vote_request(person, BILL_W, "YES"))
    await _submit(engine, vote_request(carol, BILL_W, "NO", NULLIFIER))

    # Tier-0 change stays Tier-0; Tier-0 correction stays Tier-0.
    await _submit(engine, vote_request(alice, BILL_W, "NO"))
    result = await _correct(engine, BILL_W, correction_request(bob, BILL_W, "ABSTAIN"))
    assert result["new_vote"] == "ABSTAIN"
    for person, expected in ((alice, VoteChoice.NO), (bob, VoteChoice.ABSTAIN)):
        row = await _vote_row(engine, person, BILL_W)
        assert row["vote"] == expected
        assert row["vote_nullifier"] is None and row["pk_eph"] is None


# ── Tier-1 vote changes: all fields or nothing ───────────────────────────────

_TIER1_COLUMNS = (
    "vote", "signature_hex", "pk_eph", "vote_nullifier", "linkage_tag", "timestamp_ms",
    "is_correction", "corrected_at", "original_vote", "updated_at",
)


def _snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in _TIER1_COLUMNS}


@pytest.mark.parametrize("path", ["correct", "resubmit"])
async def test_yes_to_no_with_fresh_tier1_payload_updates_all_fields(
    engine: AsyncEngine, citizens: list[Citizen], path: str,
) -> None:
    alice = citizens[0]
    t0 = int(time.time() * 1000) - 1_000
    await _submit(engine, vote_request(alice, BILL_W, "YES", NULLIFIER, timestamp_ms=t0))
    before = await _vote_row(engine, alice, BILL_W)

    fields = tier1_fields(BILL_W, "NO", NULLIFIER.upper())
    if path == "correct":
        req = voting.CorrectionRequest(
            nullifier_hash=alice.nullifier_hash, bill_id=BILL_W, vote="NO",
            signature_hex=alice.identity_signature(BILL_W, "NO"), **fields,
        )
        await _correct(engine, BILL_W, req)
    else:
        req = voting.VoteRequest(
            nullifier_hash=alice.nullifier_hash, bill_id=BILL_W, vote="NO",
            signature_hex=alice.identity_signature(BILL_W, "NO"), **fields,
        )
        await _submit(engine, req)

    after = await _vote_row(engine, alice, BILL_W)
    assert after["id"] == before["id"]
    assert after["vote"] == VoteChoice.NO
    assert after["signature_hex"] == req.signature_hex
    assert after["pk_eph"] == fields["pk_eph"] != before["pk_eph"]
    assert after["linkage_tag"] == fields["linkage_tag"] != before["linkage_tag"]
    assert after["timestamp_ms"] == fields["timestamp_ms"] > t0
    assert after["vote_nullifier"] == NULLIFIER
    if path == "correct":
        assert after["is_correction"] is True
        assert after["original_vote"] == "YES"
        assert after["corrected_at"] is not None
    assert len(await _holders(engine, NULLIFIER)) == 1


async def test_correction_nullifier_conflict_at_commit_rolls_back_everything(
    engine: AsyncEngine, citizens: list[Citizen], monkeypatch: pytest.MonkeyPatch,
) -> None:
    alice, bob, _ = citizens
    t0 = int(time.time() * 1000) - 1_000
    await _submit(engine, vote_request(alice, BILL_W, "YES", NULLIFIER, timestamp_ms=t0))
    await _submit(engine, vote_request(bob, BILL_A, "YES", OTHER_NULLIFIER))
    before = _snapshot(await _vote_row(engine, alice, BILL_W))

    # Skip the fast path so only the unique index can stop the write.
    async def precheck_passes(*_args: Any, **_kw: Any) -> bool:
        return False

    monkeypatch.setattr(voting, "_tier1_vote_nullifier_used", precheck_passes)
    with pytest.raises(HTTPException) as exc:
        await _correct(engine, BILL_W, correction_request(
            alice, BILL_W, "NO", OTHER_NULLIFIER.upper(),
        ))
    assert exc.value.status_code == 409
    assert exc.value.detail == voting.TIER1_DUPLICATE_DETAIL
    assert _snapshot(await _vote_row(engine, alice, BILL_W)) == before
    assert len(await _holders(engine, OTHER_NULLIFIER)) == 1


async def test_correction_foreign_error_rolls_back_everything(
    engine: AsyncEngine, citizens: list[Citizen],
) -> None:
    alice = citizens[0]
    t0 = int(time.time() * 1000) - 1_000
    await _submit(engine, vote_request(alice, BILL_W, "YES", NULLIFIER, timestamp_ms=t0))
    before = _snapshot(await _vote_row(engine, alice, BILL_W))
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE citizen_votes ADD CONSTRAINT ck_test_t410_vote"
            " CHECK (vote <> 'NO') NOT VALID"
        ))
    with pytest.raises(IntegrityError):
        await _correct(engine, BILL_W, correction_request(alice, BILL_W, "NO", NULLIFIER))
    assert _snapshot(await _vote_row(engine, alice, BILL_W)) == before


@pytest.mark.parametrize("path", ["correct", "resubmit"])
@pytest.mark.parametrize("stored_tier", ["tier0", "tier1"])
async def test_vote_change_never_switches_tier(
    engine: AsyncEngine, citizens: list[Citizen], path: str, stored_tier: str,
) -> None:
    alice = citizens[0]
    t0 = int(time.time() * 1000) - 1_000
    stored_nullifier = NULLIFIER if stored_tier == "tier1" else None
    await _submit(engine, vote_request(
        alice, BILL_W, "YES", stored_nullifier,
        **({"timestamp_ms": t0} if stored_nullifier else {}),
    ))
    before = _snapshot(await _vote_row(engine, alice, BILL_W))
    new_nullifier = None if stored_tier == "tier1" else NULLIFIER

    with pytest.raises(HTTPException) as exc:
        if path == "correct":
            await _correct(engine, BILL_W, correction_request(alice, BILL_W, "NO", new_nullifier))
        else:
            await _submit(engine, vote_request(alice, BILL_W, "NO", new_nullifier))
    assert exc.value.status_code == 409
    assert _snapshot(await _vote_row(engine, alice, BILL_W)) == before


@pytest.mark.parametrize("path", ["correct", "resubmit"])
async def test_replayed_or_older_tier1_payload_is_refused(
    engine: AsyncEngine, citizens: list[Citizen], path: str,
) -> None:
    alice = citizens[0]
    t0 = int(time.time() * 1000) - 1_000
    await _submit(engine, vote_request(alice, BILL_W, "YES", NULLIFIER, timestamp_ms=t0))
    before = _snapshot(await _vote_row(engine, alice, BILL_W))

    with pytest.raises(HTTPException) as exc:
        if path == "correct":
            await _correct(engine, BILL_W, correction_request(
                alice, BILL_W, "NO", NULLIFIER, timestamp_ms=t0,
            ))
        else:
            await _submit(engine, vote_request(alice, BILL_W, "NO", NULLIFIER, timestamp_ms=t0))
    assert exc.value.status_code == 400
    assert "STALE_PAYLOAD" in exc.value.detail
    assert _snapshot(await _vote_row(engine, alice, BILL_W)) == before


async def test_parallel_corrections_one_wins(engine: AsyncEngine, citizens: list[Citizen]) -> None:
    """The correction path locks the vote row: exactly one one-time correction."""
    alice = citizens[0]
    t0 = int(time.time() * 1000) - 1_000
    await _submit(engine, vote_request(alice, BILL_W, "YES", NULLIFIER, timestamp_ms=t0))
    outcomes = await asyncio.wait_for(asyncio.gather(
        _outcome(_correct(engine, BILL_W, correction_request(alice, BILL_W, "NO", NULLIFIER))),
        _outcome(_correct(engine, BILL_W, correction_request(alice, BILL_W, "ABSTAIN", NULLIFIER))),
    ), timeout=30)
    winners = [o for o in outcomes if isinstance(o, dict)]
    assert len(winners) == 1, outcomes
    assert outcomes.count(409) == 1, outcomes
    row = await _vote_row(engine, alice, BILL_W)
    assert row["vote"].value == winners[0]["new_vote"]
    assert row["original_vote"] == "YES"
