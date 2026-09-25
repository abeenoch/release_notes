from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.auth import router as auth_router
from app.api.changelogs import router as changelogs_router
from app.api.health import router as health_router
from app.api.notify_routes import router as notify_router
from app.api.public_pages import router as public_router
from app.api.repos import router as repos_router
from app.api.webhooks import router as webhooks_router
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize DB + reap stale tasks. Shutdown: clean up."""
    await init_db()
    try:
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import update

        from app.database import async_session_factory
        from app.models.changelog import Changelog as _Changelog
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        async with async_session_factory() as _db:
            await _db.execute(
                update(_Changelog)
                .where(
                    _Changelog.status.in_(["pending", "processing"]),
                    _Changelog.created_at < cutoff,
                )
                .values(status="failed", error_message="Stale task reaped on startup (server restarted before completion)")
            )
            await _db.commit()
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception("Startup reap of stale changelogs failed")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
)

# CORS for the React frontend (when running separately in dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PublicApiCorsMiddleware(BaseHTTPMiddleware):
    """Open CORS for /api/public/* ONLY — and only those endpoints are
    already unauthenticated. This is what lets the embeddable widget fetch
    a changelog page from a third-party site. Authenticated API paths keep
    the strict cors_origins list untouched; responses never carry
    credentials, so '*' is safe here."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/public"):
            response.headers.setdefault("access-control-allow-origin", "*")
        return response


# Registered AFTER CORSMiddleware → runs OUTSIDE it, so the public-path
# header is applied even when the origin isn't in cors_origins.
app.add_middleware(PublicApiCorsMiddleware)

# ── Register API routes (before static files to avoid conflicts) ──
# Note: frontend expects /api prefix (e.g. POST /api/auth/github)
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(repos_router, prefix="/api")
app.include_router(changelogs_router, prefix="/api")
app.include_router(webhooks_router, prefix="/api")
app.include_router(notify_router, prefix="/api")
app.include_router(public_router, prefix="/api")

# ── Serve the pre-built React frontend from the dist/ directory ──
_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    # Mount static assets (JS, CSS, images) at /assets
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")

    @app.get("/")
    async def serve_landing():
        """Serve the cinematic landing page at root."""
        landing = _frontend_dist / "landing.html"
        if landing.exists():
            return FileResponse(str(landing))
        # Fallback to React app if no landing page
        return FileResponse(str(_frontend_dist / "index.html"))

    # ── Favicon ───────────────────────────────────────────
    # Serve the brand favicon explicitly so it isn't swallowed by the
    # SPA catch-all below.
    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon_svg():
        favicon = _frontend_dist / "favicon.svg"
        if favicon.exists():
            return FileResponse(str(favicon), media_type="image/svg+xml")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon_ico():
        favicon = _frontend_dist / "favicon.ico"
        if favicon.exists():
            return FileResponse(str(favicon), media_type="image/x-icon")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    @app.get("/widget.js", include_in_schema=False)
    async def widget_js():
        """Embeddable changelog widget (vanilla JS + shadow DOM).

        Third-party sites include it via
        <script src="…/widget.js" data-repo="owner/repo" async></script>;
        it fetches /api/public/{owner}/{repo} (open CORS, see
        PublicApiCorsMiddleware) and renders a styled release list.
        """
        widget = _frontend_dist / "widget.js"
        if widget.exists():
            return FileResponse(str(widget), media_type="application/javascript")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """SPA fallback: serve index.html for all non-API, non-landing routes."""
        # Serve the React app for all client-side routes
        return FileResponse(str(_frontend_dist / "index.html"))

    print(f"✨ Serving landing + frontend from {_frontend_dist}")
else:
    print(f"⚠️  Frontend dist not found at {_frontend_dist} — API only")
