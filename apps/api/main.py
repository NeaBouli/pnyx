from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import identity, vaa, parliament, voting

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
            "MOD-14 Relevance",
        ]
    }

@app.get("/")
async def root():
    return {"message": "Ekklesia.gr API — εκκλησία του δήμου"}
