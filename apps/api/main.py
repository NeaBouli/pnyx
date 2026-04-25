import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)
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

scheduler = AsyncIOScheduler()


async def scheduled_scrape():
    """Scrape parliament bills every 12 hours (MOD-03 cron + MOD-10 scraper)."""
    from routers.scraper import scrape_parliament_bills
    from services.scraper_state import record_run, record_success, record_failure, is_circuit_open
    name = "parliament"
    if await is_circuit_open(name):
        logger.warning("[MOD-03] Circuit breaker OPEN for %s — skipping", name)
        return
    await record_run(name)
    try:
        bills = await scrape_parliament_bills(limit=20)
        logger.info(f"[MOD-03] Scheduled scrape: {len(bills)} bills found")
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


@asynccontextmanager
async def lifespan(app):
    # Startup
    scheduler.add_job(scheduled_scrape, IntervalTrigger(hours=12), id="parliament_scrape", replace_existing=True)
    scheduler.add_job(scheduled_notify_new_bills, IntervalTrigger(minutes=30), id="notify_new_bills", replace_existing=True)
    scheduler.add_job(scheduled_notify_results, IntervalTrigger(hours=1), id="notify_results", replace_existing=True)
    scheduler.add_job(scheduled_diavgeia_scrape, IntervalTrigger(hours=48), id="diavgeia_municipal", replace_existing=True)
    scheduler.start()
    logger.info("[Scheduler] Started — parliament 12h, diavgeia 48h, notify-bills 30m, notify-results 1h")
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ekklesia.gr",
        "https://www.ekklesia.gr",
        "https://api.ekklesia.gr",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        ]
    }

@app.get("/api/v1/version")
async def app_version():
    return {
        "version": "1.0.0",
        "versionCode": 4,
        "minSupportedCode": 3,
        "releaseNotes": {
            "el": "Έκδοση 4 — Κλειστή Δοκιμή\n• Ασφάλεια: CORS + SSH\n• Analytics διόρθωση\n• POLIS OAuth",
            "en": "Version 4 — Closed Testing\n• Security: CORS + SSH hardened\n• Analytics fix\n• POLIS OAuth",
        },
        "downloadUrl": "https://ekklesia.gr/download/ekklesia-latest.apk",
        "playStoreUrl": "https://play.google.com/store/apps/details?id=gr.ekklesia.app",
    }

@app.get("/")
async def root():
    return {"message": "Ekklesia.gr API — εκκλησία του δήμου"}
