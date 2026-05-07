from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpxyz import Response

from pyfwapi.apiconnection import APIConnection
from pyfwapi.model.collection import Collection
from pyfwapi.model.instance_info import FullAPIDescriptor
from pyfwapi.tenant import Tenant


class TestTenant:
    @pytest.fixture
    def mock_conn(self):
        conn = MagicMock(spec=APIConnection)
        conn.GET = AsyncMock()
        conn.paginated = MagicMock()
        return conn

    @pytest.fixture
    def tenant(self, mock_conn):
        return Tenant(connection=mock_conn)

    def test_tenant_init_with_creds(self):
        with patch("pyfwapi.tenant.APIConnection") as mock_api:
            tenant = Tenant(
                url="https://test.fotoware.cloud",
                client_id="id",
                client_secret="secret",
            )
            mock_api.assert_called_once_with(
                "https://test.fotoware.cloud", client_id="id", client_secret="secret"
            )
            assert tenant.api == mock_api.return_value

    def test_tenant_init_missing_creds(self):
        with pytest.raises(TypeError):
            Tenant(url="https://test.fotoware.cloud", client_id="id")  # type: ignore

    @pytest.mark.asyncio
    async def test_instance_info(self, tenant, mock_conn):
        # mock json that satisfies FullAPIDescriptor
        mock_conn.GET.return_value = Response(
            200,
            content=b"""{
            "href": "/fotoweb/me",
            "services": {
                "search": "/fotoweb/search",
                "rendition_request": "/fotoweb/renditions"
            },
            "searchURL": "/fotoweb/search{?q}"
        }""",
        )

        info = await tenant.instance_info()
        mock_conn.GET.assert_awaited_once_with("/fotoweb/me")
        assert isinstance(info, FullAPIDescriptor)

    @pytest.mark.asyncio
    async def test_iter_archives(self, tenant, mock_conn):
        async def mock_paginated(*args, **kwargs):
            yield Collection.model_validate(
                {
                    "id": "abc",
                    "name": "A",
                    "description": "",
                    "href": "/a",
                    "data": "/a/data",
                    "type": "archive",
                    "searchURL": "/a/s{?q}",
                    "originalURL": "/a/o",
                    "isSearchable": True,
                    "permissions": [],
                    "canMoveTo": True,
                    "canUploadTo": True,
                    "assetCount": 0,
                }
            )
            yield Collection.model_validate(
                {
                    "id": "def",
                    "name": "B",
                    "description": "",
                    "href": "/b",
                    "data": "/b/data",
                    "type": "archive",
                    "searchURL": "/b/s{?q}",
                    "originalURL": "/b/o",
                    "isSearchable": True,
                    "permissions": [],
                    "canMoveTo": True,
                    "canUploadTo": True,
                    "assetCount": 0,
                }
            )

        mock_conn.paginated.side_effect = mock_paginated

        archives = [a async for a in tenant.iter_archives()]
        mock_conn.paginated.assert_called_once()
        assert len(archives) == 2
        assert archives[0].id == "abc"
        assert archives[1].id == "def"
        # mock json that satisfies Collection model
        mock_conn.GET.return_value = Response(
            200,
            content=b"""{
            "id": "123",
            "name": "Test Archive",
            "description": "An archive",
            "href": "/fotoweb/archives/123",
            "data": "/fotoweb/archives/123/data",
            "type": "archive",
            "searchURL": "/fotoweb/archives/123/search{?q}",
            "originalURL": "/fotoweb/archives/123/original",
            "isSearchable": true,
            "permissions": ["read"],
            "canMoveTo": false,
            "canUploadTo": false,
            "assetCount": 10
        }""",
        )

        archive = await tenant.archive_by(id=123)
        mock_conn.GET.assert_awaited_once_with("/fotoweb/archives/123")
        assert isinstance(archive, Collection)
        assert archive.name == "Test Archive"
