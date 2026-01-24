"""Pydantic schemas for API request/response validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from infrastructure.config import DEFAULT_FETCH_INTERVAL_MINUTES


class CategoryCreate(BaseModel):
    """Schema for creating a new category."""

    name: str
    icon: str = "tag"


class CategoryResponse(BaseModel):
    """Schema for category response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    icon: str | None
    created_at: datetime


class CategoryListResponse(BaseModel):
    """Schema for category in list response with website count."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    icon: str | None
    created_at: datetime
    website_count: int


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""

    name: str | None = None
    icon: str | None = None


class WebsiteCreate(BaseModel):
    """Schema for creating a new website."""

    name: str
    url: str
    rss_url: str
    category_id: str
    fetch_interval_minutes: int = DEFAULT_FETCH_INTERVAL_MINUTES


class WebsiteResponse(BaseModel):
    """Schema for website response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    url: str
    rss_url: str
    category_id: str
    fetch_interval_minutes: int
    last_fetched_at: datetime | None
    created_at: datetime


class WebsiteListResponse(BaseModel):
    """Schema for website in list response with unread count."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    url: str
    rss_url: str
    category_id: str
    fetch_interval_minutes: int
    last_fetched_at: datetime | None
    created_at: datetime
    unread_count: int


class WebsiteUpdate(BaseModel):
    """Schema for updating a website."""

    name: str | None = None
    url: str | None = None
    rss_url: str | None = None
    category_id: str | None = None
    fetch_interval_minutes: int | None = None


class ArticleListResponse(BaseModel):
    """Schema for article in list response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    url: str
    website_id: str
    published_at: datetime | None
    fetched_at: datetime
    is_read: bool
    favorited_at: datetime | None
    reading_time_minutes: int | None


class ArticleResponse(BaseModel):
    """Schema for full article response with content."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    url: str
    content_html: str | None
    website_id: str
    published_at: datetime | None
    fetched_at: datetime
    is_read: bool
    favorited_at: datetime | None
    reading_time_minutes: int | None


class MarkReadRequest(BaseModel):
    """Schema for marking an article as read/unread."""

    is_read: bool


class MarkFavoriteRequest(BaseModel):
    """Schema for marking an article as favorite/unfavorite."""

    is_favorite: bool


class BlockDomainByArticleRequest(BaseModel):
    """Schema for blocking a domain by article ID."""

    article_id: str


class BlockDomainRequest(BaseModel):
    """Schema for blocking a domain directly."""

    domain: str


class BlockedDomainResponse(BaseModel):
    """Schema for blocked domain response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    domain: str
    created_at: datetime


class FeedDiscoveryRequest(BaseModel):
    """Schema for feed discovery request."""

    url: str


class FeedDiscoveryResponse(BaseModel):
    """Schema for feed discovery response."""

    name: str
    url: str
    rss_url: str
    description: str | None = None


class LoginRequest(BaseModel):
    """Schema for login request."""

    password: str


class ChangePasswordRequest(BaseModel):
    """Schema for password change request."""

    current_password: str
    new_password: str


class LanguageUpdate(BaseModel):
    """Schema for updating language preference."""

    language: str | None  # None means use Accept-Language header


class LanguageResponse(BaseModel):
    """Schema for language preference response."""

    language: str | None
    current: str  # The currently active language
