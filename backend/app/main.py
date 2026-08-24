import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.diagnostics import build_health_details
from app.routers import compare, discovery, ideas, implementations, papers, workspace


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Papertrail API",
    description="AI Research Workflow Tool — Backend API",
    version="0.1.0",
    lifespan=lifespan,
)

logger = logging.getLogger("papertrail")

UNEXPECTED_ERROR_DETAIL = "Internal server error."


# Registered before CORSMiddleware so it ends up inside it: Starlette makes the
# most recently added middleware the outermost. An unhandled exception that
# escapes to ServerErrorMiddleware never passes back through CORS, so the
# browser reports a CORS violation instead of the real 500 - which is what made
# the original default-user race so hard to diagnose.
@app.middleware("http")
async def catch_unhandled_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled error on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={"detail": UNEXPECTED_ERROR_DETAIL},
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(papers.router)
app.include_router(compare.router)
app.include_router(ideas.router)
app.include_router(implementations.router)
app.include_router(discovery.router)
app.include_router(workspace.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "papertrail-api"}


@app.get("/health/details")
def health_details(probe: bool = False):
    """Report configuration state.

    Pass ?probe=true to also send one minimal request to each provider, which
    is the only way to distinguish a working credential from a well-formed
    one. The probe costs a few tokens, so it is opt-in.
    """
    return build_health_details(probe=probe)
