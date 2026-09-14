"""Environment-backed application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, *, minimum: int = 1, maximum: int = 86_400) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return min(maximum, max(minimum, value))


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, default).split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    app_port: int = 8000
    db_path: str = "/data/nettodeals.db"
    admin_token: str = ""
    cookie_secure: bool = True
    admin_session_seconds: int = 28_800
    allowed_hosts: tuple[str, ...] = ("*",)
    enable_api_docs: bool = False

    awin_publisher_id: str = ""
    awin_api_token: str = ""
    awin_regions: tuple[str, ...] = ("CH",)
    awin_max_pages: int = 20

    tradedoubler_products_token: str = ""
    tradedoubler_vouchers_token: str = ""
    tradedoubler_currency: str = "CHF"
    max_products_per_feed: int = 100
    tradedoubler_max_pages: int = 10

    http_timeout: int = 20
    google_trends_enabled: bool = True
    google_trends_url: str = "https://trends.google.com/trending/rss?geo=CH"

    auto_sync_enabled: bool = True
    auto_sync_on_start: bool = True
    auto_sync_initial_delay: int = 30
    auto_sync_interval: int = 21_600

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            app_port=_int("APP_PORT", 8000, maximum=65_535),
            db_path=os.getenv("DB_PATH", "/data/nettodeals.db"),
            admin_token=os.getenv("ADMIN_TOKEN", ""),
            cookie_secure=_bool("COOKIE_SECURE", True),
            admin_session_seconds=_int("ADMIN_SESSION_SECONDS", 28_800, minimum=300),
            allowed_hosts=_csv("ALLOWED_HOSTS", "*"),
            enable_api_docs=_bool("ENABLE_API_DOCS", False),
            awin_publisher_id=os.getenv("AWIN_PUBLISHER_ID", ""),
            awin_api_token=os.getenv("AWIN_API_TOKEN", ""),
            awin_regions=_csv("AWIN_REGIONS", "CH"),
            awin_max_pages=_int("AWIN_MAX_PAGES", 20, maximum=20),
            tradedoubler_products_token=os.getenv("TRADEDOUBLER_PRODUCTS_TOKEN", ""),
            tradedoubler_vouchers_token=os.getenv("TRADEDOUBLER_VOUCHERS_TOKEN", ""),
            tradedoubler_currency=os.getenv("TRADEDOUBLER_CURRENCY", "CHF").upper(),
            max_products_per_feed=_int("MAX_PRODUCTS_PER_FEED", 100, maximum=1000),
            tradedoubler_max_pages=_int("TRADEDOUBLER_MAX_PAGES", 10, maximum=50),
            http_timeout=_int("HTTP_TIMEOUT", 20, minimum=3, maximum=120),
            google_trends_enabled=_bool("GOOGLE_TRENDS_ENABLED", True),
            google_trends_url=os.getenv(
                "GOOGLE_TRENDS_URL",
                "https://trends.google.com/trending/rss?geo=CH",
            ),
            auto_sync_enabled=_bool("AUTO_SYNC_ENABLED", True),
            auto_sync_on_start=_bool("AUTO_SYNC_ON_START", True),
            auto_sync_initial_delay=_int("AUTO_SYNC_INITIAL_DELAY", 30, minimum=1),
            auto_sync_interval=_int("AUTO_SYNC_INTERVAL", 21_600, minimum=900),
        )
