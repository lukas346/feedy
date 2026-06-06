"""Authentication router for login, logout, and password management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from api.schemas import ChangePasswordRequest, LanguageResponse, LanguageUpdate
from application.services.auth import auth_service
from i18n import SUPPORTED_LANGUAGES, create_t_function
from infrastructure.database import get_session
from infrastructure.repositories.auth_repository import AuthRepository

router = APIRouter(tags=["auth"])

# Templates will be set from main.py
templates: Jinja2Templates | None = None

COOKIE_NAME = "session_token"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days in seconds


def set_templates(t: Jinja2Templates) -> None:
    """Set the templates instance from main.py."""
    global templates
    templates = t


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    db: Annotated[Session, Depends(get_session)],
) -> Response:
    """Render the login page."""
    assert templates is not None

    # Check if already logged in
    token = request.cookies.get(COOKIE_NAME)
    if token and auth_service.validate_session(db, token):
        # Check if password change required
        if auth_service.must_change_password(db):
            return RedirectResponse(url="/change-password", status_code=302)
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse(request, "login.html")


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    db: Annotated[Session, Depends(get_session)],
    password: Annotated[str, Form()],
) -> Response:
    """Handle login form submission."""
    assert templates is not None

    if not auth_service.verify_password(db, password):
        t = create_t_function(getattr(request.state, "lang", "en"))
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": t("login.invalid_password")},
            status_code=401,
        )

    # Create session
    token = auth_service.create_session(db)

    # Check if password change is required
    if auth_service.must_change_password(db):
        response = RedirectResponse(url="/change-password", status_code=302)
    else:
        response = RedirectResponse(url="/", status_code=302)

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/logout")
def logout(
    request: Request,
    db: Annotated[Session, Depends(get_session)],
) -> Response:
    """Handle logout."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        auth_service.delete_session(db, token)

    response = RedirectResponse(url="/login?logged_out=1", status_code=302)
    response.delete_cookie(key=COOKIE_NAME)
    return response


@router.get("/change-password", response_class=HTMLResponse)
def change_password_page(
    request: Request,
    db: Annotated[Session, Depends(get_session)],
) -> Response:
    """Render the change password page."""
    assert templates is not None

    # Must be logged in
    token = request.cookies.get(COOKIE_NAME)
    if not token or not auth_service.validate_session(db, token):
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(request, "change_password.html")


@router.post("/change-password", response_class=HTMLResponse)
def change_password(
    request: Request,
    db: Annotated[Session, Depends(get_session)],
    current_password: Annotated[str, Form()],
    new_password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
) -> Response:
    """Handle password change form submission."""
    assert templates is not None

    # Must be logged in
    token = request.cookies.get(COOKIE_NAME)
    if not token or not auth_service.validate_session(db, token):
        return RedirectResponse(url="/login", status_code=302)

    t = create_t_function(getattr(request.state, "lang", "en"))

    # Validate passwords match
    if new_password != confirm_password:
        return templates.TemplateResponse(
            request,
            "change_password.html",
            {"error": t("change_password.passwords_dont_match")},
            status_code=400,
        )

    # Validate minimum length
    if len(new_password) < 4:
        return templates.TemplateResponse(
            request,
            "change_password.html",
            {"error": t("change_password.password_min_length")},
            status_code=400,
        )

    # Change password
    if not auth_service.change_password(db, current_password, new_password):
        return templates.TemplateResponse(
            request,
            "change_password.html",
            {"error": t("login.invalid_password")},
            status_code=400,
        )

    return RedirectResponse(url="/", status_code=302)


@router.post("/api/change-password")
def api_change_password(
    request: Request,
    db: Annotated[Session, Depends(get_session)],
    data: ChangePasswordRequest,
) -> dict[str, str]:
    """API endpoint for password change (used by settings page)."""
    # Must be logged in
    token = request.cookies.get(COOKIE_NAME)
    if not token or not auth_service.validate_session(db, token):
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Validate minimum length
    if len(data.new_password) < 4:
        raise HTTPException(
            status_code=400, detail="Password must be at least 4 characters"
        )

    # Change password
    if not auth_service.change_password(db, data.current_password, data.new_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    return {"message": "Password changed successfully"}


@router.get("/api/settings/language", response_model=LanguageResponse)
def get_language(
    request: Request,
    db: Annotated[Session, Depends(get_session)],
) -> LanguageResponse:
    """Get the user's language preference."""
    repo = AuthRepository(db)
    saved_language = repo.get_language()
    current_lang = getattr(request.state, "lang", "en")

    return LanguageResponse(language=saved_language, current=current_lang)


@router.post("/api/settings/language", response_model=LanguageResponse)
def set_language(
    request: Request,
    db: Annotated[Session, Depends(get_session)],
    data: LanguageUpdate,
) -> LanguageResponse:
    """Update the user's language preference."""
    # Validate language
    if data.language is not None and data.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language. Supported: {', '.join(SUPPORTED_LANGUAGES)}",
        )

    repo = AuthRepository(db)
    repo.set_language(data.language)

    # Determine current active language
    if data.language:
        current_lang = data.language
    else:
        # Fall back to Accept-Language
        from i18n import parse_accept_language

        accept_lang = request.headers.get("accept-language", "")
        current_lang = parse_accept_language(accept_lang)

    return LanguageResponse(language=data.language, current=current_lang)
