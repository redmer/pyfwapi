from unittest.mock import AsyncMock, patch

import httpxyz as httpx
import pytest

from pyfwapi.apiconnection import SEARCH_RESULT_LIMIT, APIConnection
from pyfwapi.model.asset import Asset


class TestAPIConnection:
    @pytest.fixture
    def mock_client_cls(self):
        with patch("pyfwapi.apiconnection.AsyncOAuth2Client") as MockClient:
            instance = MockClient.return_value
            instance.fetch_token = AsyncMock()
            instance.get = AsyncMock()
            instance.patch = AsyncMock()
            instance.post = AsyncMock()
            instance.aclose = AsyncMock()
            instance.token = None
            yield MockClient, instance

    @pytest.fixture
    def api_conn(self, mock_client_cls):
        _, mock_instance = mock_client_cls
        conn = APIConnection(
            "https://test.fotoware.cloud/",
            client_id="test_id",
            client_secret="test_secret",
        )
        return conn

    @pytest.mark.asyncio
    async def test_ensure_token_fetches(self, api_conn):
        assert api_conn.client.token is None
        await api_conn.ensure_token()
        api_conn.client.fetch_token.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ensure_token_skips_when_present(self, api_conn):
        api_conn.client.token = {"access_token": "abc"}
        await api_conn.ensure_token()
        api_conn.client.fetch_token.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_success(self, api_conn):
        api_conn.client.token = {"access_token": "abc"}

        mock_response = httpx.Response(
            200,
            json={"key": "value"},
            request=httpx.Request("GET", "https://test.fotoware.cloud/some/path"),
        )
        api_conn.client.get.return_value = mock_response

        resp = await api_conn.GET("/some/path", headers={"Custom": "Header"})

        api_conn.client.get.assert_awaited_once_with(
            "https://test.fotoware.cloud/some/path",
            headers={"Accept": "application/json", "Custom": "Header"},
            follow_redirects=True,
        )
        assert resp.json() == {"key": "value"}

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_get_retry_on_timeout(self, mock_sleep, api_conn):
        api_conn.client.token = {"access_token": "abc"}

        # Simulate exception on first try, then success on second
        api_conn.client.get.side_effect = [
            httpx.ConnectTimeout("timeout"),
            httpx.Response(
                200,
                json={"retry": "success"},
                request=httpx.Request("GET", "https://test.fotoware.cloud/flakey/path"),
            ),
        ]

        resp = await api_conn.GET("/flakey/path")

        assert api_conn.client.get.call_count == 2
        mock_sleep.assert_awaited_once()
        assert resp.json() == {"retry": "success"}

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_get_retry_on_transient_500(self, mock_sleep, api_conn):
        """A single transient 500 must not abort the request."""
        api_conn.client.token = {"access_token": "abc"}

        request = httpx.Request("GET", "https://test.fotoware.cloud/flakey/path?p=115")
        api_conn.client.get.side_effect = [
            httpx.Response(500, request=request),
            httpx.Response(200, json={"ok": True}, request=request),
        ]

        resp = await api_conn.GET("/flakey/path?p=115")

        assert api_conn.client.get.call_count == 2
        mock_sleep.assert_awaited_once()
        assert resp.json() == {"ok": True}

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_get_retry_burst_under_max_attempts(self, mock_sleep, api_conn):
        """A burst of fewer than 5 transient 5xx errors still succeeds."""
        api_conn.client.token = {"access_token": "abc"}

        request = httpx.Request("GET", "https://test.fotoware.cloud/flakey/path")
        api_conn.client.get.side_effect = [
            httpx.Response(500, request=request),
            httpx.Response(502, request=request),
            httpx.Response(503, request=request),
            httpx.Response(200, json={"ok": True}, request=request),
        ]

        resp = await api_conn.GET("/flakey/path")

        assert api_conn.client.get.call_count == 4
        assert mock_sleep.await_count == 3
        assert resp.json() == {"ok": True}

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_get_persistent_5xx_raises_after_max_attempts(
        self, mock_sleep, api_conn
    ):
        """Persistent 5xx raises HTTPStatusError after all attempts."""
        api_conn.client.token = {"access_token": "abc"}

        request = httpx.Request("GET", "https://test.fotoware.cloud/broken/path")
        api_conn.client.get.return_value = httpx.Response(503, request=request)

        with pytest.raises(httpx.HTTPStatusError):
            await api_conn.GET("/broken/path")

        assert api_conn.client.get.call_count == 5
        assert mock_sleep.await_count == 4

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_get_429_honors_retry_after(self, mock_sleep, api_conn):
        """A 429 with a Retry-After header waits the requested time."""
        api_conn.client.token = {"access_token": "abc"}

        request = httpx.Request("GET", "https://test.fotoware.cloud/limited/path")
        api_conn.client.get.side_effect = [
            httpx.Response(429, headers={"Retry-After": "7"}, request=request),
            httpx.Response(200, json={"ok": True}, request=request),
        ]

        resp = await api_conn.GET("/limited/path")

        assert api_conn.client.get.call_count == 2
        mock_sleep.assert_awaited_once_with(7.0)
        assert resp.json() == {"ok": True}

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_get_4xx_raises_immediately(self, mock_sleep, api_conn):
        """Client errors (other than 408/429) are not retried."""
        api_conn.client.token = {"access_token": "abc"}

        request = httpx.Request("GET", "https://test.fotoware.cloud/missing")
        api_conn.client.get.return_value = httpx.Response(404, request=request)

        with pytest.raises(httpx.HTTPStatusError):
            await api_conn.GET("/missing")

        api_conn.client.get.assert_awaited_once()
        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_patch_success(self, api_conn):
        api_conn.client.token = {"access_token": "abc"}

        mock_response = httpx.Response(
            200,
            json={"patched": True},
            request=httpx.Request("PATCH", "https://test.fotoware.cloud/patch/path"),
        )
        api_conn.client.patch.return_value = mock_response

        resp = await api_conn.PATCH("/patch/path", json={"foo": "bar"})

        api_conn.client.patch.assert_awaited_once_with(
            "https://test.fotoware.cloud/patch/path",
            headers={
                "Content-Type": "application/vnd.fotoware.assetupdate+json",
                "Accept": "application/vnd.fotoware.asset+json",
            },
            follow_redirects=True,
            json={"foo": "bar"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_post_success(self, api_conn):
        api_conn.client.token = {"access_token": "abc"}

        mock_response = httpx.Response(
            201,
            json={"created": True},
            request=httpx.Request("POST", "https://test.fotoware.cloud/post/path"),
        )
        api_conn.client.post.return_value = mock_response

        resp = await api_conn.POST("/post/path", json={"foo": "bar"})

        api_conn.client.post.assert_awaited_once_with(
            "https://test.fotoware.cloud/post/path",
            headers={"Accept": "application/json"},
            follow_redirects=False,
            json={"foo": "bar"},
        )
        assert resp.status_code == 201


class TestPaginatedSeek:
    """Seek pagination transparently restarts a search past the 10k cap."""

    LIMIT = SEARCH_RESULT_LIMIT

    @pytest.fixture
    def mock_client_cls(self):
        with patch("pyfwapi.apiconnection.AsyncOAuth2Client") as MockClient:
            instance = MockClient.return_value
            instance.fetch_token = AsyncMock()
            instance.aclose = AsyncMock()
            instance.token = {"access_token": "abc"}
            yield MockClient, instance

    @pytest.fixture
    def api_conn(self, mock_client_cls):
        conn = APIConnection(
            "https://test.fotoware.cloud/",
            client_id="test_id",
            client_secret="test_secret",
        )
        conn.GET = AsyncMock()
        return conn

    @staticmethod
    def asset_json(i: int, minute: int) -> dict:
        return {
            "href": f"/fotoweb/archives/1/asset{i}",
            "modified": f"2024-01-01T12:{minute:02d}:00Z",
            "physicalFileId": str(i),
            "linkstance": "x",
            "filename": f"asset{i}.jpg",
            "filesize": 1,
            "doctype": "image",
            "created": None,
            "archiveId": 1,
            "archiveHREF": "/fotoweb/archives/1",
            "builtinFields": [],
            "metadata": {},
            "previews": None,
            "previewToken": "x",
            "renditions": None,
            "quickRenditions": None,
        }

    def page(self, assets: list[dict]) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": assets, "paging": {}},
            request=httpx.Request("GET", "https://test.fotoware.cloud/search"),
        )

    @pytest.mark.asyncio
    async def test_paginated_single_window(self, api_conn):
        api_conn.GET.return_value = self.page([self.asset_json(i, 0) for i in range(3)])

        assets = [a async for a in api_conn.paginated("/search", type=Asset)]

        assert [a.href for a in assets] == [
            f"/fotoweb/archives/1/asset{i}" for i in range(3)
        ]
        api_conn.GET.assert_awaited_once_with("/search", headers={})

    @pytest.mark.asyncio
    async def test_paginated_seek_requeries_with_mtf(self, api_conn):
        first = [self.asset_json(i, 1) for i in range(self.LIMIT)]
        second = [self.asset_json(i, 2) for i in range(self.LIMIT, self.LIMIT + 5)]
        api_conn.GET.side_effect = [self.page(first), self.page(second)]

        assets = [
            a async for a in api_conn.paginated("/search;o=+", type=Asset, seek=True)
        ]

        assert len(assets) == self.LIMIT + 5
        assert api_conn.GET.await_count == 2
        second_url = api_conn.GET.await_args_list[1].args[0]
        assert second_url == "/search;o=+?q=mtf%3A2024-01-01T12%3A01%3A00Z"

    @pytest.mark.asyncio
    async def test_paginated_seek_appends_to_existing_query(self, api_conn):
        first = [self.asset_json(i, 1) for i in range(self.LIMIT)]
        api_conn.GET.side_effect = [self.page(first), self.page([])]

        assets = [
            a
            async for a in api_conn.paginated(
                "/search;o=+?q=fn%3A%2A.jpg", type=Asset, seek=True
            )
        ]

        assert len(assets) == self.LIMIT
        second_url = api_conn.GET.await_args_list[1].args[0]
        assert second_url == "/search;o=+?q=fn%3A%2A.jpg&q=mtf%3A2024-01-01T12%3A01%3A00Z"

    @pytest.mark.asyncio
    async def test_paginated_seek_dedupes_boundary_assets(self, api_conn):
        # all assets share the same minute: window 2 repeats the boundary asset
        first = [self.asset_json(i, 1) for i in range(self.LIMIT)]
        second = [first[-1]] + [
            self.asset_json(i, 1) for i in range(self.LIMIT, self.LIMIT + 5)
        ]
        api_conn.GET.side_effect = [self.page(first), self.page(second)]

        assets = [
            a async for a in api_conn.paginated("/search;o=+", type=Asset, seek=True)
        ]

        hrefs = [a.href for a in assets]
        assert len(assets) == self.LIMIT + 5
        assert len(hrefs) == len(set(hrefs))

    @pytest.mark.asyncio
    async def test_paginated_seek_all_duplicate_window_breaks_loop(self, api_conn):
        # >10k assets share the same timestamp: every follow-up window returns
        # only already-seen assets; the loop must terminate instead of spinning.
        first = [self.asset_json(i, 1) for i in range(self.LIMIT)]
        dupes = first[:100]
        api_conn.GET.side_effect = [self.page(first), self.page(dupes)]

        assets = [
            a async for a in api_conn.paginated("/search;o=+", type=Asset, seek=True)
        ]

        assert len(assets) == self.LIMIT
        assert api_conn.GET.await_count == 2
