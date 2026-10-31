"""Public consumers and admin decisions use persisted synthetic sensitivity flags."""
from contextlib import asynccontextmanager
from datetime import datetime
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from database import get_db
from models import BillStatus, BillStatusLog, CitizenVote, ParliamentBill, VoteChoice, ZkVoteReceipt
from routers import admin, export, notifications, parliament, zk
from services import bill_lifecycle, discourse_sync, newsletter_service, zk_arweave_publisher
from services.bill_visibility import is_public_bill
from tests.test_public_bill_snapshot import snapshot_db


@pytest.mark.parametrize("override,public", [(None, False), (False, True), (True, False)])
async def test_monthly_top_votes_excludes_flagged_bills_after_marker_removal(
    snapshot_db, monkeypatch, override: bool | None, public: bool,
) -> None:
    db = snapshot_db
    now = datetime.utcnow()
    db.add(ParliamentBill(id="S", title_el="Synthetic private decision", source="DIAVGEIA",
                         summary_long_el="Regenerated clean summary", status=BillStatus.OPEN_END,
                         sensitive_public_block=True, sensitive_override=override, created_at=now))
    db.add(CitizenVote(bill_id="S", vote=VoteChoice.YES, nullifier_hash="synthetic",
                      signature_hex="test", created_at=now))
    await db.commit()
    top_rows = []

    class ReportDb:
        scalar = db.scalar

        async def execute(self, statement, *args, **kwargs):
            if isinstance(statement, TextClause):
                statement = text(str(statement).replace("b.status::text", "CAST(b.status AS TEXT)"))
                rows = (await db.execute(statement, *args, **kwargs)).all()
                top_rows.extend(rows)
                return SimpleNamespace(all=lambda: rows)
            return await db.execute(statement, *args, **kwargs)

    @asynccontextmanager
    async def no_dispatch():
        raise newsletter_service.NewsletterLockUnavailable()
        yield  # pragma: no cover

    monkeypatch.setattr(newsletter_service, "newsletter_lock", no_dispatch)
    await newsletter_service.send_monthly_report(ReportDb())
    assert [row.id for row in top_rows] == (["S"] if public else [])


@pytest.mark.parametrize("override,public", [(None, False), (False, True), (True, False)])
async def test_zk_candidates_and_export_apply_the_shared_flag_policy(snapshot_db, override, public) -> None:
    db = snapshot_db
    db.add(ParliamentBill(id="S", title_el="Synthetic", source="PARLIAMENT", status=BillStatus.OPEN_END,
                         results_visibility="ALWAYS", sensitive_public_block=True, sensitive_override=override))
    await db.commit()
    # Only the selected scope and pending flag are needed by the candidate query.
    db.add(ZkVoteReceipt(vote_scope_id="bill:S", arweave_pending=True, vote_commitment="YES",
                         semaphore_nullifier="synthetic", merkle_root="root", merkle_depth=1,
                         signal_hash="signal", external_nullifier="external", proof_public_json={},
                         verifier_version="v", circuit_version="c", created_at=datetime.utcnow()))
    await db.commit()
    assert await zk_arweave_publisher.list_pending_public_parliament_scopes(db) == ({"bill:S"} if public else set())
    rows = await export.get_all_results(db)
    assert [row["bill_id"] for row in rows] == (["S"] if public else [])


@pytest.mark.parametrize("override,public", [(None, False), (False, True), (True, False)])
def test_lifecycle_and_zk_scope_guards_use_flags(override: bool | None, public: bool) -> None:
    bill = SimpleNamespace(id="S", source="PARLIAMENT", status=BillStatus.OPEN_END,
                           admin_hidden=None, sensitive_public_block=True, sensitive_override=override,
                           results_visibility="ALWAYS", party_votes_parliament={"P": "YES"})
    assert bill_lifecycle.is_arweave_eligible(bill)[0] is public
    assert zk._is_public_parliament_bill_scope(bill) is public
    assert zk_arweave_publisher._is_public_parliament_bill_scope(bill) is public


async def test_forum_entry_points_reject_flagged_objects_before_any_request(monkeypatch) -> None:
    bill = SimpleNamespace(admin_hidden=False, sensitive_public_block=True, sensitive_override=None)
    request = AsyncMock(side_effect=AssertionError("Private bill reached forum"))
    monkeypatch.setattr(discourse_sync, "_request_discourse", request)
    with pytest.raises(ValueError, match="not public"):
        await discourse_sync.create_discourse_topic(bill, db=None)
    assert await discourse_sync.update_discourse_topic(bill, db=None) is False
    request.assert_not_awaited()


@pytest.mark.parametrize("job,status", [("scheduled_notify_new_bills", BillStatus.ACTIVE),
                                       ("scheduled_notify_results", BillStatus.PARLIAMENT_VOTED)])
async def test_scheduled_title_notifications_filter_sensitive_bills(snapshot_db, monkeypatch, job, status) -> None:
    import main
    import database
    import redis.asyncio as aioredis
    from routers import notify
    from services import scraper_state

    db = snapshot_db
    db.add_all([ParliamentBill(id=bid, title_el="Synthetic", status=status, sensitive_public_block=blocked)
                for bid, blocked in (("PUBLIC", False), ("PRIVATE", True))])
    await db.commit()

    @asynccontextmanager
    async def connection():
        yield db

    monkeypatch.setattr(database, "AsyncSessionLocal", connection)
    cache = SimpleNamespace(exists=AsyncMock(return_value=False), setex=AsyncMock(), aclose=AsyncMock())
    monkeypatch.setattr(aioredis, "from_url", lambda *args, **kwargs: cache)
    for name in ("record_run", "record_success", "record_failure"):
        monkeypatch.setattr(scraper_state, name, AsyncMock())
    send = AsyncMock()
    monkeypatch.setattr(notify, "notify_all", send)
    await getattr(main, job)()
    assert [call.args[1]["bill_id"] for call in send.await_args_list] == ["PUBLIC"]
    scraper_state.record_failure.assert_not_awaited()


async def test_public_event_bus_rechecks_scalar_flags_and_override(snapshot_db, monkeypatch) -> None:
    db = snapshot_db
    bill = ParliamentBill(id="S", title_el="Synthetic", sensitive_public_block=False)
    db.add(bill)
    await db.commit()
    bus = notifications.EventBus()
    monkeypatch.setattr(notifications, "event_bus", bus)
    queue = bus.subscribe()
    await db.execute(text("UPDATE parliament_bills SET sensitive_public_block = true WHERE id = 'S'"))
    await db.commit()
    assert bill.sensitive_public_block is False  # Deliberately stale identity-map state.
    assert await notifications.publish_bill_event("bill.status_changed", "S", {}, db=db) is False
    assert await notifications.publish_bill_event("bill.status_changed", "S", {}) is False
    assert queue.empty()
    await db.execute(text("UPDATE parliament_bills SET sensitive_override = false WHERE id = 'S'"))
    await db.commit()
    assert await notifications.publish_bill_event("bill.status_changed", "S", {}, db=db) is True
    assert json.loads(queue.get_nowait())["bill_id"] == "S"
    await db.execute(text("UPDATE parliament_bills SET admin_hidden = true WHERE id = 'S'"))
    await db.commit()
    assert await notifications.publish_bill_event("bill.status_changed", "S", {}, db=db) is False
    assert queue.empty()


async def test_admin_transition_cannot_broadcast_a_private_bill(snapshot_db, monkeypatch) -> None:
    db = snapshot_db
    connection = await db.connection()
    await connection.run_sync(BillStatusLog.__table__.create)
    db.add(ParliamentBill(id="S", title_el="Synthetic", status=BillStatus.ACTIVE,
                         sensitive_public_block=True))
    await db.commit()
    bus = notifications.EventBus()
    monkeypatch.setattr(notifications, "event_bus", bus)
    monkeypatch.setattr("services.representation_cache.invalidate_representation_cache", AsyncMock())
    queue = bus.subscribe()
    result = await parliament.transition_bill(
        "S", parliament.TransitionRequest(new_status="WINDOW_24H"), _auth=True, db=db,
    )
    assert result["success"] is True
    assert queue.empty()


@pytest.mark.parametrize("override", [None, True, False])
@pytest.mark.parametrize("clear", [False, True])
async def test_admin_override_requires_auth_and_reason_and_calls_db_function(monkeypatch, override, clear) -> None:
    monkeypatch.setenv("ADMIN_KEY", "synthetic-admin-key")
    bill = SimpleNamespace(sensitive_public_block=True, sensitive_override=None, sensitive_override_reason=None)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: bill)),
                         refresh=AsyncMock(), commit=AsyncMock())
    invalidation = AsyncMock()
    monkeypatch.setattr("services.representation_cache.invalidate_representation_cache", invalidation)
    app = FastAPI()
    app.include_router(admin.router)
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        url = "/api/v1/admin/bills/S/sensitivity"
        body = {"sensitive_override": override, "reason": " Synthetic review ",
                "clear_sensitive_public_block": clear}
        assert (await client.patch(url, json=body)).status_code == 403
        wrong = {"Authorization": "Bearer not-the-admin-key"}
        assert (await client.patch(url, json=body, headers=wrong)).status_code == 403
        headers = {"Authorization": "Bearer synthetic-admin-key"}
        for bad in ({"sensitive_override": override}, {"sensitive_override": override, "reason": "  "},
                    {"reason": "Missing decision"}):
            assert (await client.patch(url, json=bad, headers=headers)).status_code == 422
        db.execute.assert_not_awaited()
        # The audited actor comes from the auth context, never from the request body.
        result = await client.patch(url, json={**body, "actor": "spoofed"}, headers=headers)
    assert result.status_code == 200
    assert db.execute.await_count == 2
    call = db.execute.await_args
    assert "SELECT admin_set_bill_sensitivity(" in str(call.args[0])
    assert call.args[1] == {"bill_id": "S", "override": override, "clear_flag": clear,
                            "reason": "Synthetic review", "actor": "admin_api_key"}
    # Only PostgreSQL owns mutation/auditing; the API refreshes its ORM state.
    assert bill.sensitive_override is None and bill.sensitive_public_block is True
    db.refresh.assert_awaited_once_with(bill)
    db.commit.assert_awaited_once()
    invalidation.assert_awaited_once()
