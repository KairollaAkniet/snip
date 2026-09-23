import secrets
import string
from urllib.parse import urlparse

ALPHABET = string.ascii_letters + string.digits

RESERVED_CODES = {"api", "static", "docs", "redoc", "openapi.json", "health", "favicon.ico"}


def generate_code(length: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def parse_user_agent(ua: str) -> tuple[str, str, str]:
    """Returns (device, browser, os) from a User-Agent header."""
    s = ua.lower()

    if any(bot in s for bot in ("bot", "crawler", "spider", "curl", "python-requests", "httpx")):
        device = "Bot"
    elif "ipad" in s or "tablet" in s:
        device = "Tablet"
    elif "mobi" in s or "iphone" in s or "android" in s:
        device = "Mobile"
    else:
        device = "Desktop"

    # Order matters: Edge/Opera UAs also contain "chrome", Chrome UAs contain "safari".
    if "edg/" in s:
        browser = "Edge"
    elif "opr/" in s or "opera" in s:
        browser = "Opera"
    elif "yabrowser" in s:
        browser = "Yandex"
    elif "firefox" in s or "fxios" in s:
        browser = "Firefox"
    elif "chrome" in s or "crios" in s:
        browser = "Chrome"
    elif "safari" in s:
        browser = "Safari"
    else:
        browser = "Other"

    if "windows" in s:
        os_name = "Windows"
    elif "android" in s:
        os_name = "Android"
    elif "iphone" in s or "ipad" in s or "ios" in s:
        os_name = "iOS"
    elif "mac os" in s or "macintosh" in s:
        os_name = "macOS"
    elif "linux" in s:
        os_name = "Linux"
    else:
        os_name = "Other"

    return device, browser, os_name


def referrer_domain(referrer: str | None) -> str:
    if not referrer:
        return "Direct"
    host = urlparse(referrer).hostname
    if not host:
        return "Direct"
    return host.removeprefix("www.")[:255]
