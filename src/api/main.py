from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)

from api.routers import (
    articles,
    auth,
    blocked_domains,
    categories,
    epub,
    opml,
    pages,
    websites,
)
from application.services.auth import auth_service
from i18n import (
    SUPPORTED_LANGUAGES,
    create_t_function,
    parse_accept_language,
)
from infrastructure.config import (
    DEFAULT_LOAD_MORE_SIZE,
    DEFAULT_PAGE_SIZE,
    get_git_commit,
    settings,
)
from infrastructure.database import engine, session_scope
from infrastructure.repositories.auth_repository import AuthRepository
from infrastructure.logging import setup_logging

setup_logging(name="app")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://fonts.gstatic.com; "
            "frame-src 'self' "
            "https://*.youtube.com https://*.youtube-nocookie.com "
            "https://*.vimeo.com https://player.vimeo.com "
            "https://*.dailymotion.com "
            "https://*.twitch.tv https://player.twitch.tv "
            "https://clips.twitch.tv "
            "https://*.ted.com https://embed.ted.com; "
            "frame-ancestors 'none'"
        )
        return response


# Routes that don't require authentication
PUBLIC_PATHS = {"/login", "/logout", "/health", "/static"}


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that requires authentication for protected routes."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Allow public paths
        if path in PUBLIC_PATHS or path.startswith("/static/"):
            return await call_next(request)

        # Check session token
        token = request.cookies.get("session_token")
        with session_scope() as db:
            if not token or not auth_service.validate_session(db, token):
                # Return 401 for API requests, redirect for page requests
                if path.startswith("/api/"):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Not authenticated"},
                    )
                return RedirectResponse(url="/login", status_code=302)

            # Check password requirements except for the change-password page.
            must_change_password = auth_service.must_change_password(db)
            if path != "/change-password" and must_change_password:
                if path.startswith("/api/"):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Password change required"},
                    )
                return RedirectResponse(
                    url="/change-password",
                    status_code=302,
                )
        return await call_next(request)


class LanguageMiddleware(BaseHTTPMiddleware):
    """Middleware that determines the language for each request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Default language
        lang = "en"
        db_language: Optional[str] = None

        # Try to get user's saved language preference from database
        token = request.cookies.get("session_token")
        if token:
            with session_scope() as db:
                repo = AuthRepository(db)
                db_language = repo.get_language()

        # Determine language by user preference, header, then default.
        if db_language and db_language in SUPPORTED_LANGUAGES:
            lang = db_language
        else:
            accept_lang = request.headers.get("accept-language", "")
            lang = parse_accept_language(accept_lang)

        # Store language in request state for use in templates
        request.state.lang = lang
        request.state.user_language_set = db_language is not None

        return await call_next(request)


# Base directory for static files and templates
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


def i18n_context_processor(request: Request) -> dict[str, Any]:
    """Context processor that provides i18n context for all templates."""
    lang = getattr(request.state, "lang", "en")
    user_language_set = getattr(request.state, "user_language_set", False)
    return {
        "t": create_t_function(lang),
        "current_lang": lang,
        "user_language_set": user_language_set,
    }


# Jinja2 templates configuration with i18n context processor
templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR),
    context_processors=[i18n_context_processor],
)

# Add supported languages, git commit, and base URL to template globals
templates.env.globals["SUPPORTED_LANGUAGES"] = SUPPORTED_LANGUAGES
# Lowercase alias for templates that use snake-case naming.
templates.env.globals["supported_languages"] = SUPPORTED_LANGUAGES
templates.env.globals["GIT_COMMIT"] = get_git_commit()
templates.env.globals["BASE_URL"] = settings.base_url
templates.env.globals["PAGE_SIZE"] = DEFAULT_PAGE_SIZE
templates.env.globals["LOAD_MORE_SIZE"] = DEFAULT_LOAD_MORE_SIZE

# Set templates for routers
pages.set_templates(templates)
auth.set_templates(templates)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup: ensure database connection works
    with engine.connect():
        pass
    yield
    # Shutdown: dispose engine connections
    engine.dispose()


app = FastAPI(
    title="Feedy",
    description="RSS feed reader and article converter",
    version="0.1.0",
    lifespan=lifespan,
)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Authentication middleware (added after security headers)
app.add_middleware(AuthMiddleware)

# Language middleware (added after auth middleware)
app.add_middleware(LanguageMiddleware)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include routers
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(articles.router)
app.include_router(blocked_domains.router)
app.include_router(categories.router)
app.include_router(websites.router)
app.include_router(opml.router)
app.include_router(epub.router)


@app.get("/health", response_model=dict[str, str])
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
