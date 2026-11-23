import http.client
import re
import urllib.request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

UA = "Mozilla/5.0 (compatible; taxi-plan/1.0)"
TIMEOUT_S = 20
ALIVE_TIMEOUT_S = 10  # allowed exception to the 20 s rule: a dead-link check should be quick
GONE_CODES = (404, 410)


class SourceError(Exception):
    pass


_QUERY = re.compile(r"(https?://[^\s?#]+)\?\S*")
_PATH = re.compile(r"(?<![\w/])(?:[A-Za-z]:[\\/]|/(?:Users|home)/)[^\s'\"<>|]*")


def clean(text: str) -> str:
    """Text bound for plan.json or logs: no URL query strings (API key) and no absolute local paths. Never truncates."""
    return _PATH.sub("<path>", _QUERY.sub(r"\1", text))


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
