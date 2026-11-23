import http.client
import urllib.request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

UA = "Mozilla/5.0 (compatible; taxi-plan/1.0)"
TIMEOUT_S = 20
ALIVE_TIMEOUT_S = 10  # allowed exception to the 20 s rule: a dead-link check should be quick
GONE_CODES = (404, 410)


class SourceError(Exception):
    pass


def _req(url: str, method: str = "GET") -> urllib.request.Request:
    return urllib.request.Request(url, method=method, headers={"User-Agent": UA})


def get_text(url: str, timeout: int = TIMEOUT_S) -> str:
    host = urlsplit(url).netloc  # messages carry the host only: the query may hold an API key
    try:
        with urllib.request.urlopen(_req(url), timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        raise SourceError(f"{host}: HTTP {e.code}") from None
    except (URLError, OSError) as e:
        raise SourceError(f"{host}: {type(e).__name__}") from None


def url_alive(url: str, timeout: int = ALIVE_TIMEOUT_S) -> bool:
    """False only when the link is gone (404/410) or unreachable; other HTTP errors (403 etc.) count as alive."""
    try:
        urllib.request.urlopen(_req(url, "HEAD"), timeout=timeout).close()
        return True
    except HTTPError as e:
        return e.code not in GONE_CODES
    except (URLError, OSError, ValueError, http.client.HTTPException):  # stalls, resets, scheme-less links
        return False
