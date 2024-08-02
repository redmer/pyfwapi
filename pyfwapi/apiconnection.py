import asyncio
import typing as t
import urllib.parse

import aiolimiter
from authlib.integrations.httpx_client import AsyncOAuth2Client
from httpx import Response

from pyfwapi.errors import APIError
from pyfwapi.log import pyfwapiLog
from pyfwapi.model.basemodel import APIResponse


class APIConnection:
    # For implementers, this class only concerns itself with the OAuth2 token,
    # and proxies such GET, POST, PATCH requests. It doesn't know about specific
    # entity types, like Asset or Rendition.

    def __init__(
        self, endpoint_url: str, *, client_id: str, client_secret: str
    ) -> None:
        """
        Connect to an instance of the FotoWare API.

        Args:
            endpoint_url: URL of the endpoint, e.g. `https://myorg.example.org`
            client_id: the registered non-interactive application's `client_id`
            client_secret: the application's secret
        """

        self.HOST = endpoint_url.removesuffix("/")
        self.TOKEN_ENDPOINT = f"{self.HOST}/fotoweb/oauth2/token"
        self.rate_limit = aiolimiter.AsyncLimiter(1, 0.8)

        self.client = AsyncOAuth2Client(
            client_id=client_id,
            client_secret=client_secret,
            token_endpoint_auth_method="client_secret_post",
            token_endpoint=self.TOKEN_ENDPOINT,
            grant_type="client_credentials",
        )

    async def ensure_token(self):
        """Ensure that the OAuth2 client has fetched a token."""
        # AsyncOAuth2Clien locks to ensure no race conditions when fetching the token.
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
        self, path: str, /, *, headers: t.Mapping[str, str] = {}, **kwargs
    ) -> Response:
        """
        Perform GET request on the API and return JSON.

        Raises:
            httpx.HTTPStatusError: API response if the status code is not 200.
        """
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

    async def PATCH(
        self,
        path: str,
        /,
        *,
        headers: t.Mapping[str, str] = {},
        json: t.Any = {},
        **kwargs,
    ) -> Response:
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
        json: t.Any = {},
        **kwargs,
    ) -> Response:
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
        self, path: str, /, *, type: type[T], headers: t.Mapping[str, str] = {}
    ) -> t.AsyncGenerator[T, None]:
        """
        Iterate over "data" items in any paged resource.

        Args:
            path: the resource endpoint, starting with /
            type: the response JSON type (APIResponse)
            headers: arbitrary HTTP headers for this request
        """
        page_url: str | None = path

        while page_url is not None or page_url != "":
            full_results = await self.GET(page_url, headers=headers)
            full_results = full_results.json()

            # Some first pages are different
            page: t.Mapping[str, t.Any] = full_results.get("assets", full_results)
            data = page.get("data", [])

            if len(data) == 0:
                break
            for d in data:
                yield type.model_validate(d)

            # For next iteration, set page_url to None or next page
            page_url = None
            page_url: str | None = page.get("paging", dict()).get("next", None)

    async def retrying(
        self, path: str, *, retries: int | None = None, delay: float | None = None
    ) -> Response:
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
