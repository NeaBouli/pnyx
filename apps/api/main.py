from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import identity, vaa, parliament, voting
from routers import arweave
from routers import scraper
from routers import public_api
from routers import export
from routers import analytics
from routers import mp
from routers import govgr

app = FastAPI(
    title="Ekklesia.gr API",
    description="Ψηφιακή Πλατφόρμα Αμέσης Δημοκρατίας — Backend API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://ekklesia.gr"],
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
        ]
    }

@app.get("/")
async def root():
    return {"message": "Ekklesia.gr API — εκκλησία του δήμου"}
