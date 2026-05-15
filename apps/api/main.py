import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)
local_error_logger = logging.getLogger("ekklesia.errors")

# ── Sentry Cloud Integration (Hybrid: Cloud + lokaler Fallback) ──────────────
SENTRY_ENABLED = False
_SENTRY_DSN = os.getenv("SENTRY_DSN_API", "")

if _SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        def _before_send_filter(event, hint):
            """GDPR: keine PII senden."""
            if "request" in event:
                event["request"].pop("env", None)
                headers = event.get("request", {}).get("headers", {})
                if isinstance(headers, dict):
                    headers.pop("X-Forwarded-For", None)
                    headers.pop("Cookie", None)
            return event

        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            integrations=[FastApiIntegration(), StarletteIntegration()],
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
            send_default_pii=False,
            before_send=_before_send_filter,
        )
        SENTRY_ENABLED = True
        logger.info("[SENTRY] Cloud aktiv — %s", os.getenv("SENTRY_ENVIRONMENT", "production"))
    except Exception as e:
        logger.warning("[SENTRY] Init fehlgeschlagen — lokaler Fallback: %s", e)


def capture_error(error: Exception, context: dict = None):
    """Hybrid: Sentry wenn aktiv, sonst lokal loggen."""
    if SENTRY_ENABLED:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            if context:
                for k, v in context.items():
                    scope.set_extra(k, v)
            sentry_sdk.capture_exception(error)
    else:
        local_error_logger.error("[LOCAL] %s: %s | %s", type(error).__name__, error, context)

def _get_real_ip(request: Request) -> str:
    """Extract real client IP from X-Forwarded-For (behind Traefik)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=_get_real_ip, default_limits=["60/minute"])
from routers import identity, vaa, parliament, voting
from routers import arweave
from routers import scraper
from routers import public_api
from routers import export
from routers import analytics
from routers import mp
from routers import govgr
from routers import admin
from routers import notifications
from routers import municipal
from routers import payments
from routers import newsletter
from routers import contact
from routers import notify
from routers import diavgeia
from routers import agent
from routers import polis_qr
from routers import sso
from routers import claude_agent
from routers import cplm
from routers import app_version

scheduler = AsyncIOScheduler()


async def scheduled_scrape():
    """Scrape parliament bills every 12 hours (MOD-03 cron + MOD-10 scraper).
    Fetches from hellenicparliament.gr API and upserts new bills into DB.
    """
    from routers.scraper import scrape_parliament_bills
    from services.scraper_state import record_run, record_success, record_failure, is_circuit_open
    from database import AsyncSessionLocal
    from models import ParliamentBill, BillStatus
    from sqlalchemy import select
    import hashlib

    name = "parliament"
    if await is_circuit_open(name):
        logger.warning("[MOD-03] Circuit breaker OPEN for %s — skipping", name)
        await record_run(name)
        return
    await record_run(name)
    try:
        bills = await scrape_parliament_bills(limit=20)
        logger.info(f"[MOD-03] Scheduled scrape: {len(bills)} bills fetched from API")

        if not bills:
            await record_success(name)
            return

        inserted = 0
        async with AsyncSessionLocal() as db:
            for b in bills:
                title = (b.get("title_el") or "").strip()
                if not title or len(title) < 10:
                    continue

                # Generate stable ID: law_num > law_id (from Jina URL) > title hash
                law_num = b.get("law_num")
                law_id = b.get("law_id")  # UUID from parliament URL
                if law_num:
                    bill_id = f"GR-{law_num}".replace(" ", "-")[:50]
                elif law_id:
                    bill_id = f"GR-{law_id[:8]}"
                else:
                    h = hashlib.sha256(title.encode()).hexdigest()[:8]
                    bill_id = f"GR-AUTO-{h}"

                # Skip if already exists
                existing = await db.execute(
                    select(ParliamentBill.id).where(ParliamentBill.id == bill_id)
                )
                if existing.scalar_one_or_none():
                    continue

                # Parse vote date if available (strip tz for naive DB column)
                vote_date = None
                if b.get("date"):
                    try:
                        from datetime import datetime as dt
                        vote_date = dt.fromisoformat(b["date"]).replace(tzinfo=None)
                    except (ValueError, TypeError):
                        pass

                # Parse submitted_date (strip tz for naive DB column)
                submitted_date = None
                if b.get("submitted_date"):
                    try:
                        from datetime import datetime as dt
                        submitted_date = dt.fromisoformat(b["submitted_date"]).replace(tzinfo=None)
                    except (ValueError, TypeError):
                        pass

                new_bill = ParliamentBill(
                    id=bill_id,
                    title_el=title,
                    status=BillStatus.ANNOUNCED,
                    parliament_url=b.get("url"),
                    parliament_vote_date=vote_date,
                    submitted_date=submitted_date,
                    categories=[b["ministry"]] if b.get("ministry") else None,
                )
                db.add(new_bill)
                inserted += 1

            if inserted > 0:
                await db.commit()
                logger.info("[MOD-03] Upserted %d new bills into DB", inserted)
                # Notify community about new bills
                try:
                    from services.telegram_community import notify_announced
                    for b in bills[:inserted]:
                        title = (b.get("title_el") or "")[:150]
                        if title:
                            await notify_announced(b.get("law_id", "")[:8] or "new", title, b.get("submitted_date"))
                except Exception as e:
                    logger.warning("[MOD-03] Telegram notify failed: %s", e)

        await record_success(name)
    except Exception as e:
        logger.error(f"[MOD-03] Scheduled scrape failed: {e}")
        await record_failure(name, str(e))


async def scheduled_notify_new_bills():
    """Check for new ACTIVE bills and push-notify registered devices."""
    import redis.asyncio as aioredis
    from sqlalchemy import select
    from database import AsyncSessionLocal
    from models import ParliamentBill, BillStatus
    from routers.notify import notify_all
    from services.scraper_state import record_run, record_success, record_failure

    name = "notify_new_bills"
    await record_run(name)
    try:
        r = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ParliamentBill).where(ParliamentBill.status == BillStatus.ACTIVE)
            )
            for bill in result.scalars().all():
                key = f"notified:new_bill:{bill.id}"
                if await r.exists(key):
                    continue
                await notify_all("new_bill", {
                    "title": "🗳️ Νέα Ψηφοφορία",
                    "body": bill.title_el[:100],
                    "bill_id": bill.id,
                })
                await r.setex(key, 604800, "1")  # 7 days TTL
                logger.info(f"[MOD-20] Notified: new bill {bill.id}")
        await r.aclose()
        await record_success(name)
    except Exception as e:
        logger.error(f"[MOD-20] Notify new bills failed: {e}")
        await record_failure(name, str(e))


async def scheduled_notify_results():
    """Check for new PARLIAMENT_VOTED bills and push-notify results."""
    import redis.asyncio as aioredis
    from sqlalchemy import select
    from database import AsyncSessionLocal
    from models import ParliamentBill, BillStatus
    from routers.notify import notify_all
    from services.scraper_state import record_run, record_success, record_failure

    name = "notify_results"
    await record_run(name)
    try:
        r = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ParliamentBill).where(ParliamentBill.status == BillStatus.PARLIAMENT_VOTED)
            )
            for bill in result.scalars().all():
                key = f"notified:result:{bill.id}"
                if await r.exists(key):
                    continue
                await notify_all("result", {
                    "title": "📊 Αποτέλεσμα Ψηφοφορίας",
                    "body": bill.title_el[:100],
                    "bill_id": bill.id,
                })
                await r.setex(key, 604800, "1")
                logger.info(f"[MOD-20] Notified: result {bill.id}")
        await r.aclose()
        await record_success(name)
    except Exception as e:
        logger.error(f"[MOD-20] Notify results failed: {e}")
        await record_failure(name, str(e))


async def scheduled_diavgeia_scrape():
    """Scrape Diavgeia municipal decisions every 48h (MOD-21)."""
    from services.scraper_state import record_run, record_success, record_failure, is_circuit_open
    from services.diavgeia_scraper import scrape_decisions
    from database import AsyncSessionLocal

    name = "diavgeia_municipal"
    if await is_circuit_open(name):
        logger.warning("[MOD-21] Circuit breaker OPEN for %s — skipping", name)
        await record_run(name)
        return
    await record_run(name)
    try:
        async with AsyncSessionLocal() as session:
            result = await scrape_decisions(
                session=session,
                decision_type_uids=["Α.1.1", "Α.2", "2.4.1", "2.4.2"],
                max_pages=5,
                dry_run=False,
            )
            logger.info("[MOD-21] Scheduled Diavgeia scrape: %d fetched, %d inserted, %d errors",
                        result.fetched, result.inserted, len(result.errors))
            if result.errors:
                logger.warning("[MOD-21] Scrape errors: %s", result.errors[:3])
        await record_success(name)
    except Exception as e:
        logger.error("[MOD-21] Scheduled Diavgeia scrape failed: %s", e)
        await record_failure(name, str(e))


async def scheduled_forum_sync():
    """Sync bills to Discourse forum every 10 min."""
    from services.discourse_sync import sync_new_bills_to_forum, FORUM_SYNC_ENABLED, DISCOURSE_API_KEY
    from services.scraper_state import record_run, record_success, record_failure
    name = "forum_sync"
    if not FORUM_SYNC_ENABLED or not DISCOURSE_API_KEY:
        await record_run(name)
        await record_success(name)
        logger.debug("[Forum] Sync disabled — recording idle state")
        return
    await record_run(name)
    from database import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            await sync_new_bills_to_forum(db)
        await record_success(name)
    except Exception as e:
        logger.error("[Forum] Sync failed: %s", e)
        await record_failure(name, str(e))


async def scheduled_bill_lifecycle():
    """Auto-transition bills based on parliament_vote_date (every 1h)."""
    from services.bill_lifecycle import run_bill_lifecycle
    from services.scraper_state import record_run, record_success, record_failure
    from database import AsyncSessionLocal
    name = "bill_lifecycle"
    await record_run(name)
    try:
        async with AsyncSessionLocal() as db:
            stats = await run_bill_lifecycle(db)
            if stats["transitioned"] > 0:
                logger.info("[LIFECYCLE] %s", stats)
        await record_success(name)
    except Exception as e:
        logger.error("[LIFECYCLE] Failed: %s", e)
        await record_failure(name, str(e))


async def scheduled_cplm_refresh():
    """Refresh CPLM aggregate cache every 6 hours."""
    from services.cplm import refresh_cplm_cache
    from services.scraper_state import record_run, record_success, record_failure
    from database import AsyncSessionLocal
    name = "cplm_refresh"
    await record_run(name)
    try:
        async with AsyncSessionLocal() as db:
            result = await refresh_cplm_cache(db)
            logger.info("[CPLM] Refreshed: x=%.4f y=%.4f voters=%d", result["x"], result["y"], result["total_voters"])
        await record_success(name)
    except Exception as e:
        logger.error("[CPLM] Refresh failed: %s", e)
        await record_failure(name, str(e))


async def scheduled_greek_topics():
    """Scrape Greek news RSS and create forum topics every 6 hours."""
    from services.scraper_state import record_run, record_success, record_failure, is_circuit_open
    name = "greek_topics"
    try:
        from services.greek_topics_scraper import scrape_greek_topics, GREEK_SCRAPER_ENABLED
    except ImportError:
        logger.debug("[GreekScraper] Module nicht verfuegbar — Job deaktiviert")
        await record_run(name)
        await record_success(name)
        return

    if not GREEK_SCRAPER_ENABLED:
        await record_run(name)
        await record_success(name)
        logger.debug("[GreekScraper] Disabled — recording idle state")
        return
    if await is_circuit_open(name):
        logger.warning("[GreekScraper] Circuit breaker OPEN — skipping")
        return
    await record_run(name)
    try:
        stats = await scrape_greek_topics()
        logger.info("[GreekScraper] %s", stats)
        await record_success(name)
    except Exception as e:
        logger.error("[GreekScraper] Failed: %s", e)
        await record_failure(name, str(e))


@asynccontextmanager
async def lifespan(app):
    # Startup
    scheduler.add_job(scheduled_scrape, IntervalTrigger(hours=12), id="parliament_scrape", replace_existing=True)
    scheduler.add_job(scheduled_notify_new_bills, IntervalTrigger(minutes=30), id="notify_new_bills", replace_existing=True)
    scheduler.add_job(scheduled_notify_results, IntervalTrigger(hours=1), id="notify_results", replace_existing=True)
    scheduler.add_job(scheduled_diavgeia_scrape, IntervalTrigger(hours=48), id="diavgeia_municipal", replace_existing=True)
    scheduler.add_job(scheduled_forum_sync, IntervalTrigger(minutes=10), id="forum_sync", replace_existing=True)
    scheduler.add_job(scheduled_bill_lifecycle, IntervalTrigger(hours=1), id="bill_lifecycle", replace_existing=True)
    scheduler.add_job(scheduled_cplm_refresh, IntervalTrigger(hours=6), id="cplm_refresh", replace_existing=True)
    scheduler.add_job(scheduled_greek_topics, IntervalTrigger(hours=6), id="greek_topics", replace_existing=True)
    scheduler.start()
    logger.info("[Scheduler] Started — lifecycle 1h, parliament 12h, diavgeia 48h, notify-bills 30m, notify-results 1h, forum-sync 10m, greek-topics 6h")
    yield
    # Shutdown
    scheduler.shutdown()
    logger.info("[Scheduler] Shut down")


_is_dev = os.getenv("ENVIRONMENT", "production") != "production"

app = FastAPI(
    title="Ekklesia.gr API",
    description="Ψηφιακή Πλατφόρμα Αμέσης Δημοκρατίας — Backend API",
    version="0.1.0",
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
    openapi_url="/openapi.json" if _is_dev else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ekklesia.gr",
        "https://www.ekklesia.gr",
        "https://api.ekklesia.gr",
        "https://dashboard.ekklesia.gr",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_noindex_header(request: Request, call_next):
    """Prevent search engines from indexing API responses."""
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


app.include_router(identity.router)
app.include_router(vaa.router)
app.include_router(parliament.router)
app.include_router(voting.router)
app.include_router(arweave.router)
app.include_router(scraper.router)
app.include_router(public_api.router)
app.include_router(export.router)
app.include_router(analytics.router)
app.include_router(mp.router)
app.include_router(govgr.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(municipal.router)
app.include_router(payments.router)
app.include_router(newsletter.router)
app.include_router(contact.router)
app.include_router(notify.router)
app.include_router(diavgeia.router)
app.include_router(agent.router)
app.include_router(polis_qr.router)
app.include_router(sso.router)
app.include_router(claude_agent.router)
app.include_router(cplm.router)
app.include_router(app_version.router)

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "ekklesia-api",
        "version": "0.1.0",
        "modules": [
            "MOD-01 Identity",
            "MOD-02 VAA",
            "MOD-03 Parliament",
            "MOD-04 CitizenVote",
            "MOD-05 Analytics/Divergence",
            "MOD-12 PublicAPI",
            "MOD-08 Arweave",
            "MOD-10 AI Scraper",
            "MOD-11 Public API",
            "MOD-06 Analytics",
            "MOD-09 gov.gr OAuth",
            "MOD-12 MP Comparison",
            "MOD-14 Data Export",
            "MOD-14 Relevance",
            "MOD-07 Notifications",
            "MOD-15 Admin Panel",
            "MOD-16 Municipal Governance",
            "MOD-18 Community Donations",
            "MOD-19 Newsletter (Listmonk + Brevo)",
            "MOD-20 Push Notifications",
            "MOD-21 Diavgeia Integration",
            "MOD-22 RAG Agent (Ollama + DeepL)",
            "MOD-23 Greek Topics Scraper",
            "MOD-24 CPLM (Citizens Political Liquid Mirror)",
        ]
    }

@app.get("/api/v1/health/modules")
async def health_modules():
    """Detailed per-module health status for live wiki indicators."""
    import redis.asyncio as aioredis
    import httpx

    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    r = aioredis.from_url(redis_url, decode_responses=True)

    modules = {}

    # Helper: check scraper state from Redis
    async def scraper_status(name: str) -> dict:
        try:
            err_count = int(await r.get(f"scraper:{name}:error_count") or 0)
            last_ok = await r.get(f"scraper:{name}:last_success")
            last_err = await r.get(f"scraper:{name}:last_error")
            if err_count >= 3:
                return {"status": "error", "error": last_err or "circuit breaker open", "error_count": err_count}
            if err_count > 0:
                return {"status": "degraded", "error": last_err, "error_count": err_count}
            return {"status": "ok", "last_success": last_ok}
        except Exception:
            return {"status": "ok"}

    # MOD-01 Identity
    modules["MOD-01"] = {"name": "HLR Identity", "status": "ok"}

    # MOD-02 VAA
    modules["MOD-02"] = {"name": "VAA Compass", "status": "ok"}

    # MOD-03 Parliament Scraper
    parl = await scraper_status("parliament")
    modules["MOD-03"] = {"name": "Parliament Scraper", **parl}

    # MOD-04 CitizenVote
    modules["MOD-04"] = {"name": "Citizen Vote", "status": "ok"}

    # MOD-05 Divergence
    modules["MOD-05"] = {"name": "Divergence Score", "status": "ok"}

    # MOD-06 Analytics
    modules["MOD-06"] = {"name": "Analytics", "status": "ok"}

    # MOD-07 Notifications
    modules["MOD-07"] = {"name": "Notifications", "status": "ok"}

    # MOD-08 Arweave
    modules["MOD-08"] = {"name": "Arweave Archive", "status": "ok"}

    # MOD-09 gov.gr
    modules["MOD-09"] = {"name": "gov.gr OAuth", "status": "deferred"}

    # MOD-10 AI Scraper
    modules["MOD-10"] = {"name": "AI Scraper", "status": "ok"}

    # MOD-11 Public API
    modules["MOD-11"] = {"name": "Public API", "status": "ok"}

    # MOD-12 MP Comparison
    modules["MOD-12"] = {"name": "MP Comparison", "status": "ok"}

    # MOD-14 Relevance + Export
    modules["MOD-14"] = {"name": "Relevance + Export", "status": "ok"}

    # MOD-15 Admin
    modules["MOD-15"] = {"name": "Admin Panel", "status": "ok"}

    # MOD-16 Municipal
    modules["MOD-16"] = {"name": "Municipal Governance", "status": "ok"}

    # MOD-18 Stripe
    modules["MOD-18"] = {"name": "Community Donations", "status": "ok"}

    # MOD-19 Newsletter
    modules["MOD-19"] = {"name": "Newsletter", "status": "ok"}

    # MOD-20 Push
    modules["MOD-20"] = {"name": "Push Notifications", "status": "ok"}

    # MOD-21 Diavgeia
    diav = await scraper_status("diavgeia_municipal")
    modules["MOD-21"] = {"name": "Diavgeia Integration", **diav}

    # MOD-22 Ollama + DeepL
    try:
        from services.ollama_service import ollama_available, deepl_available
        ollama_ok = await ollama_available()
        deepl_ok = await deepl_available()
        if ollama_ok and deepl_ok:
            modules["MOD-22"] = {"name": "RAG Agent (Ollama + DeepL)", "status": "ok", "ollama": True, "deepl": True}
        elif ollama_ok:
            modules["MOD-22"] = {"name": "RAG Agent (Ollama + DeepL)", "status": "degraded", "ollama": True, "deepl": False, "error": "DeepL unavailable"}
        else:
            modules["MOD-22"] = {"name": "RAG Agent (Ollama + DeepL)", "status": "error", "ollama": False, "deepl": deepl_ok, "error": "Ollama offline"}
    except Exception as e:
        modules["MOD-22"] = {"name": "RAG Agent", "status": "error", "error": str(e)}

    # MOD-23 Greek Topics Scraper
    greek_enabled = os.getenv("GREEK_SCRAPER_ENABLED", "false").lower() == "true"
    if greek_enabled:
        greek_st = await scraper_status("greek_topics")
        modules["MOD-23"] = {"name": "Greek Topics Scraper", **greek_st}
    else:
        modules["MOD-23"] = {"name": "Greek Topics Scraper", "status": "disabled"}

    # Overall
    active_statuses = [m["status"] for m in modules.values() if m["status"] not in ("disabled", "deferred")]
    if "error" in active_statuses:
        overall = "error"
    elif "degraded" in active_statuses:
        overall = "degraded"
    else:
        overall = "ok"

    return {"modules": modules, "overall": overall, "total": len(modules)}


@app.get("/api/v1/version")
async def legacy_app_version():
    """Legacy endpoint — redirects to canonical /api/v1/app/version data."""
    from routers.app_version import LATEST_VERSION, LATEST_VERSION_CODE, MIN_REQUIRED_VERSION_CODE
    from routers.app_version import RELEASE_NOTES_EL, RELEASE_NOTES_EN, PLAYSTORE_URL, DIRECT_APK_URL
    return {
        "version": LATEST_VERSION,
        "versionCode": LATEST_VERSION_CODE,
        "minSupportedCode": MIN_REQUIRED_VERSION_CODE,
        "releaseNotes": {"el": RELEASE_NOTES_EL, "en": RELEASE_NOTES_EN},
        "downloadUrl": DIRECT_APK_URL,
        "playStoreUrl": "https://play.google.com/store/apps/details?id=ekklesia.gr",
    }

@app.get("/api/v1/admin/sentry/status")
async def sentry_status():
    """Sentry Cloud Status fuer Dashboard."""
    return {
        "enabled": SENTRY_ENABLED,
        "dsn_configured": bool(_SENTRY_DSN),
        "environment": os.getenv("SENTRY_ENVIRONMENT", "unknown"),
        "traces_sample_rate": float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        "provider": "sentry.io Cloud" if SENTRY_ENABLED else "lokaler Fallback",
    }


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    """Block all crawlers from indexing the API subdomain."""
    return PlainTextResponse(
        "User-agent: *\nDisallow: /\n",
        media_type="text/plain",
    )


@app.get("/")
async def root():
    return {"message": "Ekklesia.gr API — εκκλησία του δήμου"}
