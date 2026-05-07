from unittest.mock import AsyncMock, patch

import httpxyz as httpx
import pytest

from pyfwapi.apiconnection import APIConnection


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
        mock_sleep.assert_awaited_once_with(60)
        assert resp.json() == {"retry": "success"}

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
