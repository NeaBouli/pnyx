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

scheduler = AsyncIOScheduler()


async def scheduled_scrape():
    """Scrape parliament bills every 6 hours (MOD-03 cron + MOD-10 scraper)."""
    from routers.scraper import scrape_parliament_bills
    try:
        bills = await scrape_parliament_bills(limit=20)
        logger.info(f"[MOD-03] Scheduled scrape: {len(bills)} bills found")
    except Exception as e:
        logger.error(f"[MOD-03] Scheduled scrape failed: {e}")


@asynccontextmanager
async def lifespan(app):
    # Startup
    scheduler.add_job(scheduled_scrape, IntervalTrigger(hours=6), id="parliament_scrape", replace_existing=True)
    scheduler.start()
    logger.info("[MOD-03] APScheduler started — parliament scrape every 6h")
    yield
    # Shutdown
    scheduler.shutdown()
    logger.info("[MOD-03] APScheduler shut down")


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
