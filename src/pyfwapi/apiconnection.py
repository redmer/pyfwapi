import asyncio
import random
import typing as t
import urllib.parse
from datetime import UTC
from urllib.parse import quote

import aiolimiter
import httpxyz as httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client

from pyfwapi.errors import APIError
from pyfwapi.log import pyfwapiLog
from pyfwapi.model.basemodel import APIResponse

# Transient HTTP statuses worth retrying on idempotent GETs.
# Other 4xx are client errors and must raise immediately.
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})

# Transport-level errors that may be retried.
RETRYABLE_TRANSPORT_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
)

MAX_GET_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_MAX_SECONDS = 16.0

# The server caps search results at this many assets.
SEARCH_RESULT_LIMIT = 10_000


def _backoff_delay(attempt: int) -> float:
    """Exponential backoff with jitter: ~1s, 2s, 4s, 8s, 16s."""
    delay = min(BACKOFF_BASE_SECONDS * 2**attempt, BACKOFF_MAX_SECONDS)
    return delay + random.uniform(0, delay * 0.5)


def _retry_after(response: httpx.Response) -> float | None:
    """Parse a numeric `Retry-After` response header, if present."""
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return min(float(value), BACKOFF_MAX_SECONDS)
    except ValueError:
        return None


class APIConnection:
    # For implementers, this class only concerns itself with the OAuth2 token,
    # and proxies such GET, POST, PATCH requests. It doesn't know about specific
    # entity types, like Asset or Rendition.

    def __init__(
        self,
        endpoint_url: str,
        *,
        client_id: str,
        client_secret: str,
        max_rate: float = 1,
        time_period: float = 0.8,
    ) -> None:
        """
        Connect to an instance of the FotoWare API.

        Args:
            endpoint_url: URL of the endpoint, e.g. `https://myorg.example.org`
            client_id: the registered non-interactive application's `client_id`
            client_secret: the application's secret
            max_rate: number of requests allowed per `time_period` (client-side
                rate limit; defaults to the conservative 1 request / 0.8 s).
            time_period: period in seconds over which `max_rate` requests are
                allowed.
        """

        self.HOST = endpoint_url.removesuffix("/")
        self.TOKEN_ENDPOINT = f"{self.HOST}/fotoweb/oauth2/token"
        self.rate_limit = aiolimiter.AsyncLimiter(max_rate, time_period)

        self.client = AsyncOAuth2Client(
            client_id=client_id,
            client_secret=client_secret,
            token_endpoint_auth_method="client_secret_post",
            token_endpoint=self.TOKEN_ENDPOINT,
            grant_type="client_credentials",
        )

    async def ensure_token(self):
        """Ensure that the OAuth2 client has fetched a token."""
        # AsyncOAuth2Client locks to ensure no race conditions when fetching the token.
        if not self.client.token:
            await self.client.fetch_token()  # type: ignore

    def __del__(self):
        # Close connection when this object is destroyed...
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.client.aclose())
            else:
                loop.run_until_complete(self.client.aclose())
        except Exception:
            pass

    async def GET(
        self,
        path: str,
        /,
        *,
        headers: t.Mapping[str, str] = {},
        **kwargs,
    ) -> httpx.Response:
        """
        Perform GET request on the API and return JSON.

        GETs are idempotent, so transient failures (HTTP 408/429/5xx and
        transport-level connection errors) are retried with exponential
        backoff and jitter. Other 4xx responses raise immediately.

        Raises:
            httpx.HTTPStatusError: API response if the status code is not 200.
            httpx.ConnectTimeout: Server side rate limit exceeded
            httpx.RemoteProtocolError: Server side rate limit exceeded
        """
        last_error: BaseException | None = None

        for attempt in range(MAX_GET_ATTEMPTS):
            try:
                await self.ensure_token()
                pyfwapiLog.debug(f"GET {urllib.parse.unquote(path)}")
                async with self.rate_limit:
                    r = await self.client.get(
                        self.HOST + path,
                        headers={"Accept": "application/json", **headers},
                        follow_redirects=True,
                        **kwargs,
                    )
                    r.raise_for_status()
                    return r

            except httpx.HTTPStatusError as e:
                # Non-retryable client errors (e.g. 401/403/404) raise at once.
                if e.response.status_code not in RETRYABLE_STATUS_CODES:
                    raise
                last_error = e
                reason = f"HTTP {e.response.status_code}"
                delay = _retry_after(e.response) or _backoff_delay(attempt)

            except RETRYABLE_TRANSPORT_ERRORS as e:
                # A possible effect of the server-side rate limiter.
                last_error = e
                reason = f"{type(e).__name__}: {e}"
                delay = _backoff_delay(attempt)
                # Refresh the token on the next attempt; the connection
                # reset may have invalidated the session state.
                self.client.token = None

            if attempt < MAX_GET_ATTEMPTS - 1:
                pyfwapiLog.warning(
                    "Transient error on GET %s: %s. Retrying attempt %d/%d in %.1fs.",
                    urllib.parse.unquote(path),
                    reason,
                    attempt + 2,
                    MAX_GET_ATTEMPTS,
                    delay,
                )
                await asyncio.sleep(delay)

        pyfwapiLog.error(
            "GET %s failed after %d attempts.",
            urllib.parse.unquote(path),
            MAX_GET_ATTEMPTS,
        )
        assert last_error is not None
        raise last_error

    async def PATCH(
        self,
        path: str,
        /,
        *,
        headers: t.Mapping[str, str] = {},
        json: t.Any | None = None,
        **kwargs,
    ) -> httpx.Response:
        """
        Perform PATCH request on the API and return JSON.

        Args:
            path: the resource endpoint, starting with /
            headers: arbitrary HTTP headers for this request
            data: any JSON data to be sent along

        Raises:
            httpx.HTTPStatusError: API response if the status code is not 2xx.
        """
        await self.ensure_token()
        pyfwapiLog.debug(f"PATCH {urllib.parse.unquote(path)}")
        async with self.rate_limit:
            r = await self.client.patch(
                self.HOST + path,
                headers={
                    "Content-Type": "application/vnd.fotoware.assetupdate+json",
                    "Accept": "application/vnd.fotoware.asset+json",
                    **headers,
                },
                follow_redirects=True,
                json=json,
                **kwargs,
            )
            r.raise_for_status()
            return r

    async def POST(
        self,
        path: str,
        /,
        *,
        headers: t.Mapping[str, str] = {},
        json: t.Any | None = None,
        **kwargs,
    ) -> httpx.Response:
        """
        Perform POST request on the API and return JSON.

        Args:
            path: the resource endpoint, starting with /
            headers: arbitrary HTTP headers for this request
            data: any JSON data to be sent along

        Raises:
            httpx.HTTPStatusError: if API response is not 2xx
        """
        await self.ensure_token()
        pyfwapiLog.debug(f"POST {urllib.parse.unquote(path)}")
        async with self.rate_limit:
            r = await self.client.post(
                self.HOST + path,
                headers={"Accept": "application/json", **headers},
                json=json,
                follow_redirects=False,
                **kwargs,
            )
            r.raise_for_status()
            return r

    async def paginated[T: APIResponse](
        self,
        path: str,
        /,
        *,
        type: type[T],
        headers: t.Mapping[str, str] = {},
        seek: bool = False,
    ) -> t.AsyncGenerator[T, None]:
        """
        Iterate over "data" items in any paged resource.

        Args:
            path: the resource endpoint, starting with /
            type: the response JSON type (APIResponse)
            headers: arbitrary HTTP headers for this request
            seek: work around the server's 10k search-result cap. When a window
                is exhausted at the cap, restart the search narrowed with `mtf`
                (modified from) set to the last seen modification time. Requires
                ascending modification order (`;o=+`) and items exposing
                `href`/`modified` (i.e. Assets). Boundary assets may repeat
                (`mtf` is inclusive, minute precision), so assets are deduped per href.
        """
        last_modified: str | None = None
        seen_hrefs: set[str] = set()

        while True:
            url = path
            if last_modified is not None:
                joiner = "&" if "?" in path else "?"
                url = f"{path}{joiner}q=mtf%3A{quote(last_modified)}"

            raw = 0
            yielded = 0
            page_url: str | None = url
            while page_url:
                full_results = await self.GET(page_url, headers=headers)
                full_results = full_results.json()

                # Some first pages are different
                page: t.Mapping[str, t.Any] = full_results.get("assets", full_results)
                data = page.get("data", [])

                if len(data) == 0:
                    break
                for d in data:
                    raw += 1
                    item = type.model_validate(d)
                    if seek:
                        modified = getattr(item, "modified", None)
                        if modified is not None:
                            last_modified = modified.astimezone(UTC).strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            )
                        href: str = item.href  # type: ignore[attr-defined]
                        if href in seen_hrefs:
                            continue
                        seen_hrefs.add(href)
                    yield item
                    yielded += 1

                paging = page.get("paging", {})
                if paging:
                    page_url = paging.get("next")
                else:
                    page_url = None

            # Stop when a window made no progress (all results were duplicates,
            # e.g. >10k assets share the boundary timestamp) or when the window
            # was not capped by the server, meaning the results are exhausted.
            if not seek or yielded == 0 or raw < SEARCH_RESULT_LIMIT:
                break

    async def retrying(
        self, path: str, *, retries: int | None = None, delay: float | None = None
    ) -> httpx.Response:
        """
        GET and upon non-200, retry to get the binary stream of a file.

        Args:
            path: the local tenant-local path to the resource
            retries: number of retries (default: 10)
            delay: how to long to waiting between retries (in seconds)

        Raises:
            httpx.HTTPStatusError: API response if the status code is not 200.
            pyfwapi.errors.APIError: The response was 200, but still no success.
        """

        retries = retries if retries is not None else 10
        delay = delay if delay is not None else 5

        await self.ensure_token()

        while retries > 0:
            resp = await self.client.get(self.HOST + path)
            if resp.status_code == 200:
                # 200 OK: rendition is ready
                return resp

            if resp.status_code != 202:
                # 202 Accepted: the rendition is not ready yet
                retries -= 1

            retries -= 1
            await asyncio.sleep(delay)

        pyfwapiLog.error(f"Download '{path}' failed after {retries}")
        resp.raise_for_status()
        raise APIError(f"Download '{path}' failed after {retries}")
