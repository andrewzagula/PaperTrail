from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import discovery, papers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    init_db()
    yield


app = FastAPI(
    title="Papertrail API",
    description="AI Research Workflow Tool — Backend API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(papers.router)
app.include_router(discovery.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "papertrail-api"}
