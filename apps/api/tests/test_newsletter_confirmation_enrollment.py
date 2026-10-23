"""Confirmation survives a campaign acquiring the lease before enrollment."""
import asyncio
import json
import logging
from unittest.mock import AsyncMock

import pytest

from routers import newsletter, newsletter_admin
from services.newsletter_audience import CampaignPlan, audit_audience
from services.newsletter_consent import CONFIRMED_KEY, BREVO_ADD_RETRY_KEY
from services.newsletter_lock import newsletter_lock
from tests.test_newsletter_audiences import (
    provider, store, seed_campaign, consent, dispatch, EMAIL,
)


@pytest.mark.parametrize("kind", ["monthly", "admin"])
async def test_campaign_between_confirmation_and_enrollment_excludes_pending_contact_and_backfill_recovers(
    store, provider, monkeypatch, caplog, kind,
):
    seed_campaign(store, provider)
    email = "New.Confirmation@example.org"
    token_key = "newsletter:pending:enrollment-race"
    store.pending[token_key] = json.dumps(consent(email))
    enrollment_started = asyncio.Event()
    campaign_locked = asyncio.Event()
    confirmation_returned = asyncio.Event()
    original_sync = newsletter._sync_brevo_contact

    async def sync(*args, **kwargs):
        enrollment_started.set()
        await campaign_locked.wait()
        return await original_sync(*args, **kwargs)

    async def competing_campaign():
        await enrollment_started.wait()
        async with newsletter_lock(store):
            campaign_locked.set()
            await confirmation_returned.wait()
            return await dispatch(kind)

    monkeypatch.setattr(newsletter, "_sync_brevo_contact", sync)
    campaign = asyncio.create_task(competing_campaign())
    try:
        response = await asyncio.wait_for(newsletter.confirm_subscription("enrollment-race"), timeout=5)
        assert response.status_code == 200
        assert token_key not in store.pending
        assert email in store.hashes[CONFIRMED_KEY]
        assert store.hashes[BREVO_ADD_RETRY_KEY][email] == "1"
        assert email.casefold() not in provider.contacts
        with caplog.at_level(logging.INFO, logger="services.newsletter_audience"):
            confirmation_returned.set()
            result = await asyncio.wait_for(campaign, timeout=5)
    finally:
        campaign.cancel()
        await asyncio.gather(campaign, return_exceptions=True)

    if kind == "monthly":
        assert result is True
    else:
        assert result["sent"] == 1 and result["excluded"] == 1
    assert "reason=sent selected=1 excluded=1 failed=0 provider=1" in caplog.text
    assert email not in caplog.text
    assert provider.delivered == [{EMAIL}]
    assert store.hashes[BREVO_ADD_RETRY_KEY][email] == "1"
    monkeypatch.setattr(newsletter, "_sync_brevo_contact", original_sync)
    assert await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True) == {
        "to_add": 1, "already_present": 1, "held": 0, "failed": 0,
    }
    assert not store.hashes[BREVO_ADD_RETRY_KEY]
    assert email.casefold() in provider.contacts
    audience = await audit_audience(store, CampaignPlan())
    assert audience.selected == {EMAIL, email.casefold()}


@pytest.mark.parametrize("kind", ["monthly", "admin"])
async def test_cancellation_after_consent_commit_retains_enrollment_for_backfill(store, provider, monkeypatch, kind):
    seed_campaign(store, provider)
    email = "cancelled-confirmation@example.org"
    token_key = "newsletter:pending:cancelled-enrollment"
    store.pending[token_key] = json.dumps(consent(email))
    original_sync = newsletter._sync_brevo_contact
    monkeypatch.setattr(newsletter, "_sync_brevo_contact", AsyncMock(side_effect=asyncio.CancelledError))

    with pytest.raises(asyncio.CancelledError):
        await newsletter.confirm_subscription("cancelled-enrollment")
    assert token_key not in store.pending
    assert email in store.hashes[CONFIRMED_KEY]
    assert store.hashes[BREVO_ADD_RETRY_KEY][email] == "1"
    assert email not in provider.contacts
    await dispatch(kind)
    assert provider.delivered == [{EMAIL}]
    monkeypatch.setattr(newsletter, "_sync_brevo_contact", original_sync)
    result = await newsletter_admin.newsletter_backfill(dry_run=False, _auth=True)
    assert result["to_add"] == 1 and result["failed"] == 0
    assert not store.hashes[BREVO_ADD_RETRY_KEY]
    assert email in provider.contacts
