"""HTML pages router for rendering templates."""

import re
import unicodedata
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from api.schemas import FeedDiscoveryRequest, FeedDiscoveryResponse
from application.services.domain_utils import extract_domain
from application.services.feed_discovery import (
    FeedDiscoveryError,
    feed_discovery_service,
)
from application.services.validators import validate_url
from application.workers.fetch_articles import ArticleFetcher
from i18n import create_t_function
from infrastructure.config import (
    DEFAULT_FETCH_INTERVAL_MINUTES,
    DEFAULT_LOAD_MORE_SIZE,
    DEFAULT_PAGE_SIZE,
)
from infrastructure.database import get_session
from infrastructure.repositories import (
    ArticleRepository,
    BlockedDomainRepository,
    CategoryRepository,
    WebsiteRepository,
)

router = APIRouter(tags=["pages"])

# Templates will be set from main.py
templates: Jinja2Templates | None = None


def set_templates(t: Jinja2Templates) -> None:
    """Set the templates instance from main.py."""
    global templates
    templates = t


def _get_categories_with_articles(
    session: Session, limit_per_category: int = DEFAULT_PAGE_SIZE
) -> list[dict[str, Any]]:
    """Get all categories with their articles (from all websites in each category)."""
    category_repo = CategoryRepository(session)
    website_repo = WebsiteRepository(session)
    article_repo = ArticleRepository(session)

    categories = category_repo.get_all()

    result = []
    for category in categories:
        website_ids = website_repo.get_ids_by_category(category.id)

        if not website_ids:
            continue

        articles, total_count, has_more = (
            article_repo.get_unread_for_category_paginated(
                website_ids, limit=limit_per_category
            )
        )

        result.append(
            {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "icon": category.icon,
                "unread_count": total_count,
                "articles": articles,
                "total_count": total_count,
                "has_more": has_more,
            }
        )

    return result


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Render the feeds page (home page)."""
    assert templates is not None
    return templates.TemplateResponse(request, "feeds.html")


@router.get("/feeds/list", response_class=HTMLResponse)
def feeds_list(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Render the feeds list partial for HTMX."""
    assert templates is not None
    categories = _get_categories_with_articles(session)
    return templates.TemplateResponse(
        request,
        "partials/htmx/feeds_list.html",
        {"categories": categories},
    )


@router.post("/feeds/categories/{category_id}/read-all", response_class=HTMLResponse)
def mark_category_articles_read(
    request: Request,
    category_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Mark all articles from a category as read and refresh the feeds list."""
    assert templates is not None

    category_repo = CategoryRepository(session)
    category = category_repo.get_by_id(category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    website_repo = WebsiteRepository(session)
    website_ids = website_repo.get_ids_by_category(category_id)
    article_repo = ArticleRepository(session)
    article_repo.mark_all_as_read_for_websites(website_ids)

    categories = _get_categories_with_articles(session)
    return templates.TemplateResponse(
        request,
        "partials/htmx/feeds_list.html",
        {"categories": categories, "show_success_popup": True},
    )


@router.get("/articles", response_class=HTMLResponse)
def articles_page(
    request: Request,
    website_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Render the articles page for a specific website."""
    assert templates is not None
    repo = WebsiteRepository(session)
    website = repo.get_by_id(website_id)
    if website is None:
        return HTMLResponse(content="Website not found", status_code=404)
    return templates.TemplateResponse(
        request,
        "articles.html",
        {"website": website},
    )


@router.get("/articles/list", response_class=HTMLResponse)
def articles_list(
    request: Request,
    website_id: str,
    session: Annotated[Session, Depends(get_session)],
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
    show_success_popup: bool = False,
) -> HTMLResponse:
    """Render the articles list partial for HTMX."""
    assert templates is not None

    repo = ArticleRepository(session)
    articles, total_count, has_more = repo.get_for_website(
        website_id, limit=limit, offset=offset
    )

    remaining = max(0, total_count - offset - len(articles))

    return templates.TemplateResponse(
        request,
        "partials/htmx/articles_list.html",
        {
            "articles": articles,
            "website_id": website_id,
            "limit": limit,
            "next_offset": offset + limit,
            "has_more": has_more,
            "remaining": remaining,
            "show_success_popup": show_success_popup,
        },
    )


@router.post("/articles/{website_id}/read-all", response_class=HTMLResponse)
def mark_website_articles_read(
    request: Request,
    website_id: str,
    session: Annotated[Session, Depends(get_session)],
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> HTMLResponse:
    """Mark all articles from a website as read and refresh the article list."""
    website_repo = WebsiteRepository(session)
    website = website_repo.get_by_id(website_id)
    if website is None:
        raise HTTPException(status_code=404, detail="Website not found")

    article_repo = ArticleRepository(session)
    article_repo.mark_all_as_read_for_website(website_id)

    return articles_list(
        request,
        website_id,
        session,
        limit=limit,
        offset=offset,
        show_success_popup=True,
    )


@router.get("/articles/more", response_class=HTMLResponse)
def articles_more(
    request: Request,
    website_id: str,
    session: Annotated[Session, Depends(get_session)],
    offset: int = DEFAULT_PAGE_SIZE,
    limit: int = DEFAULT_LOAD_MORE_SIZE,
) -> HTMLResponse:
    """Load more articles for a website."""
    assert templates is not None

    repo = ArticleRepository(session)
    articles, total_count, has_more = repo.get_for_website(
        website_id, limit=limit, offset=offset
    )

    remaining = max(0, total_count - offset - len(articles))

    return templates.TemplateResponse(
        request,
        "partials/htmx/articles_more.html",
        {
            "articles": articles,
            "website_id": website_id,
            "offset": offset + len(articles),
            "limit": limit,
            "has_more": has_more,
            "remaining": remaining,
        },
    )


@router.get("/article/{article_id}", response_class=HTMLResponse)
def reader_page(
    request: Request,
    article_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Render the article reader page."""
    assert templates is not None

    article_repo = ArticleRepository(session)
    website_repo = WebsiteRepository(session)

    article = article_repo.get_by_id(article_id)
    if article is None:
        return HTMLResponse(content="Article not found", status_code=404)

    website = website_repo.get_by_id(article.website_id)

    # Mark article as read when viewing
    if not article.is_read:
        article_repo.mark_as_read(article, is_read=True)

    # Get domain for display
    article_domain = article.domain or extract_domain(article.url)

    return templates.TemplateResponse(
        request,
        "reader.html",
        {
            "article": article,
            "website": website,
            "content_html": article.content_html,
            "article_domain": article_domain,
        },
    )


@router.get("/favorites", response_class=HTMLResponse)
def favorites_page(request: Request) -> HTMLResponse:
    """Render the favorites page showing all favorited articles."""
    assert templates is not None
    return templates.TemplateResponse(request, "favorites.html")


@router.get("/favorites/list", response_class=HTMLResponse)
def favorites_list(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    page: int = 1,
    q: str | None = None,
) -> HTMLResponse:
    """Render the favorites list partial with pagination and search."""
    assert templates is not None

    per_page = DEFAULT_PAGE_SIZE
    offset = (page - 1) * per_page
    search_query = q.strip() if q else ""
    is_search = q is not None  # True if search input triggered this request

    repo = ArticleRepository(session)
    articles, total_count, has_more = repo.get_favorites(
        limit=per_page, offset=offset, search_query=search_query
    )

    total_pages = (total_count + per_page - 1) // per_page if total_count else 1

    return templates.TemplateResponse(
        request,
        "partials/htmx/favorites_list.html",
        {
            "articles": articles,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "has_more": has_more,
            "search_query": search_query,
            "is_search": is_search,
        },
    )


@router.get("/feeds/more", response_class=HTMLResponse)
def feeds_more(
    request: Request,
    category_id: str,
    session: Annotated[Session, Depends(get_session)],
    offset: int = DEFAULT_PAGE_SIZE,
    limit: int = DEFAULT_LOAD_MORE_SIZE,
) -> HTMLResponse:
    """Load more articles for a category in the feeds."""
    assert templates is not None

    website_repo = WebsiteRepository(session)
    article_repo = ArticleRepository(session)

    website_ids = website_repo.get_ids_by_category(category_id)
    articles, total_count, has_more = article_repo.get_unread_for_category_paginated(
        website_ids=website_ids,
        limit=limit,
        offset=offset,
    )

    remaining = max(0, total_count - offset - len(articles))

    return templates.TemplateResponse(
        request,
        "partials/htmx/feeds_more.html",
        {
            "articles": articles,
            "category_id": category_id,
            "offset": offset + len(articles),
            "limit": limit,
            "has_more": has_more,
            "remaining": remaining,
        },
    )


@router.get("/subscriptions", response_class=HTMLResponse)
def subscriptions_page(request: Request) -> HTMLResponse:
    """Render the subscriptions page listing all feeds."""
    assert templates is not None
    return templates.TemplateResponse(request, "subscriptions.html")


@router.get("/subscriptions/list", response_class=HTMLResponse)
def subscriptions_list(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Render the subscriptions list partial for HTMX."""
    assert templates is not None

    repo = WebsiteRepository(session)
    websites_query = repo.get_all_with_category_names()

    # Group websites by category
    categories_dict: dict[str, dict[str, object]] = {}
    for website, category_name, category_icon in websites_query:
        cat_name = category_name or "Uncategorized"
        cat_icon = category_icon or "tag"
        if cat_name not in categories_dict:
            categories_dict[cat_name] = {
                "id": website.category_id,
                "name": cat_name,
                "icon": cat_icon,
                "websites": [],
            }
        websites_list: list[object] = categories_dict[cat_name][
            "websites"
        ]  # type: ignore[assignment]
        websites_list.append(website)

    # Convert to list sorted by category name
    categories = list(categories_dict.values())

    return templates.TemplateResponse(
        request,
        "partials/htmx/subscriptions_list.html",
        {"categories": categories},
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request) -> HTMLResponse:
    """Render the settings page."""
    assert templates is not None
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"default_fetch_interval_minutes": DEFAULT_FETCH_INTERVAL_MINUTES},
    )


@router.get("/settings/categories", response_class=HTMLResponse)
def settings_categories_list(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Render the categories list partial for settings page."""
    assert templates is not None

    repo = CategoryRepository(session)
    categories_query = repo.get_all_with_website_counts()

    categories = [
        {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "icon": cat.icon,
            "website_count": website_count,
        }
        for cat, website_count in categories_query
    ]

    return templates.TemplateResponse(
        request,
        "partials/htmx/settings_categories.html",
        {"categories": categories},
    )


@router.get("/settings/categories/options", response_class=HTMLResponse)
def settings_category_options(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Render the category options for dropdown."""
    assert templates is not None
    repo = CategoryRepository(session)
    categories = repo.get_all()
    return templates.TemplateResponse(
        request,
        "partials/htmx/category_options.html",
        {"categories": categories},
    )


@router.get("/settings/websites", response_class=HTMLResponse)
def settings_websites_list(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Render the websites list partial for settings page."""
    assert templates is not None

    repo = WebsiteRepository(session)
    websites_query = repo.get_all_with_category_names()

    # Group websites by category
    categories_dict: dict[str, dict[str, object]] = {}
    for website, category_name, category_icon in websites_query:
        cat_name = category_name or "Uncategorized"
        cat_icon = category_icon or "tag"
        if cat_name not in categories_dict:
            categories_dict[cat_name] = {
                "name": cat_name,
                "icon": cat_icon,
                "websites": [],
            }
        websites_list: list[dict[str, object]] = categories_dict[cat_name][
            "websites"
        ]  # type: ignore[assignment]
        websites_list.append(
            {
                "id": website.id,
                "name": website.name,
                "url": website.url,
                "rss_url": website.rss_url,
                "category_id": website.category_id,
                "category_name": cat_name,
                "fetch_interval_minutes": website.fetch_interval_minutes,
                "last_fetched_at": website.last_fetched_at,
            }
        )

    # Convert to list sorted by category name
    categories = list(categories_dict.values())

    return templates.TemplateResponse(
        request,
        "partials/htmx/settings_websites.html",
        {"categories": categories},
    )


def _generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from a name."""
    normalized = unicodedata.normalize("NFKD", name)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\s-]", "", ascii_text).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug


@router.post("/settings/categories", response_class=HTMLResponse)
def create_category_form(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    name: Annotated[str, Form()],
    icon: Annotated[str, Form()] = "tag",
) -> HTMLResponse:
    """Create a category from form data (for HTMX)."""
    assert templates is not None

    repo = CategoryRepository(session)
    repo.create(name=name, slug=_generate_slug(name), icon=icon)

    # Return updated categories list
    return settings_categories_list(request, session)


@router.post("/settings/websites", response_class=HTMLResponse)
def create_website_form(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    name: Annotated[str, Form()],
    url: Annotated[str, Form()],
    rss_url: Annotated[str, Form()],
    category_id: Annotated[str, Form()],
    fetch_interval_minutes: Annotated[int, Form()] = DEFAULT_FETCH_INTERVAL_MINUTES,
) -> HTMLResponse:
    """Create a website from form data (for HTMX)."""
    assert templates is not None

    # Validate URLs
    if not validate_url(url) or not validate_url(rss_url):
        t = create_t_function(getattr(request.state, "lang", "en"))
        error_msg = t("common.invalid_url")
        return HTMLResponse(
            content=f"<div class='text-red-600'>{error_msg}</div>",
            status_code=400,
        )

    repo = WebsiteRepository(session)

    # Check for duplicate RSS URL
    existing = repo.get_by_rss_url(rss_url)
    if existing is not None:
        t = create_t_function(getattr(request.state, "lang", "en"))
        error_msg = t("settings.feeds.duplicate_rss_url")
        return HTMLResponse(
            content=f"<div class='text-red-600'>{error_msg}</div>",
            status_code=409,
        )

    repo.create(
        name=name,
        url=url,
        rss_url=rss_url,
        category_id=category_id,
        fetch_interval_minutes=fetch_interval_minutes,
    )

    # Return updated websites list
    return settings_websites_list(request, session)


@router.post("/settings/fetch-all", response_class=HTMLResponse)
def fetch_all_feeds(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Trigger fetching articles from all websites."""
    assert templates is not None

    fetcher = ArticleFetcher()
    new_articles = fetcher.fetch_all(session)

    return templates.TemplateResponse(
        request,
        "partials/htmx/fetch_result.html",
        {"new_articles": new_articles},
    )


@router.post("/settings/websites/{website_id}/refetch", response_class=HTMLResponse)
def refetch_website(
    request: Request,
    website_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Force refetch all articles from a specific website."""
    assert templates is not None

    fetcher = ArticleFetcher()
    try:
        new_articles = fetcher.force_refetch_website(website_id, session)
    except ValueError:
        raise HTTPException(status_code=404, detail="Website not found")

    return templates.TemplateResponse(
        request,
        "partials/htmx/fetch_result.html",
        {"new_articles": new_articles, "refetch": True},
    )


@router.post("/settings/websites/{website_id}/unread-all", response_class=HTMLResponse)
def unread_all_website_articles(
    request: Request,
    website_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Mark all articles from a specific website as unread."""
    assert templates is not None

    website_repo = WebsiteRepository(session)
    website = website_repo.get_by_id(website_id)
    if website is None:
        raise HTTPException(status_code=404, detail="Website not found")

    article_repo = ArticleRepository(session)
    count = article_repo.mark_all_as_unread_for_website(website_id)

    return templates.TemplateResponse(
        request,
        "partials/htmx/unread_result.html",
        {"count": count},
    )


@router.get("/settings/blocked-domains", response_class=HTMLResponse)
def settings_blocked_domains_list(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Render the blocked domains list partial for settings page."""
    assert templates is not None

    repo = BlockedDomainRepository(session)
    blocked_domains = repo.get_all()

    return templates.TemplateResponse(
        request,
        "partials/htmx/settings_blocked_domains.html",
        {"blocked_domains": blocked_domains},
    )


@router.post("/api/discover-feed", response_model=FeedDiscoveryResponse)
def discover_feed(data: FeedDiscoveryRequest) -> FeedDiscoveryResponse:
    """
    Discover feed information from a URL.

    Takes a website URL or feed URL and returns feed metadata including
    the site name, website URL, RSS feed URL, and description.
    """
    try:
        result = feed_discovery_service.discover(data.url)
        return FeedDiscoveryResponse(
            name=result.name,
            url=result.url,
            rss_url=result.rss_url,
            description=result.description,
        )
    except FeedDiscoveryError as e:
        raise HTTPException(status_code=400, detail=str(e))
