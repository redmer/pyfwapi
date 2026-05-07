from unittest.mock import AsyncMock, MagicMock

import httpxyz as httpx
import pytest

from pyfwapi.apiconnection import APIConnection
from pyfwapi.change.stateful import (
    BaseChangeManager,
    ChangeTask,
    MetadataRequest,
    MoveRequest,
    UploadRequest,
)


class TestStatefulBase:
    @pytest.fixture
    def mock_conn(self):
        conn = MagicMock(spec=APIConnection)
        conn.PATCH = AsyncMock()
        conn.POST = AsyncMock()
        conn.GET = AsyncMock()
        return conn

    @pytest.fixture
    def base_manager(self):
        return BaseChangeManager()

    @pytest.mark.asyncio
    async def test_commit_uncommitted_metadata_success(self, base_manager, mock_conn):
        task = ChangeTask(
            change=MetadataRequest("href", {1: {"value": "test"}}), status="uncommitted"
        )
        base_manager.add_task(task)

        # Mock the PATCH response to succeed
        mock_conn.PATCH.return_value = httpx.Response(200)

        await base_manager.commit_uncommitted(task, conn=mock_conn)

        assert task.status == "done"
        mock_conn.PATCH.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_commit_uncommitted_metadata_failure(self, base_manager, mock_conn):
        task = ChangeTask(
            change=MetadataRequest("href", {1: {"value": "test"}}), status="uncommitted"
        )
        base_manager.add_task(task)

        # Mock the PATCH response to raise HTTPStatusError
        error_response = httpx.Response(400, request=httpx.Request("PATCH", "url"))
        mock_conn.PATCH.side_effect = httpx.HTTPStatusError(
            "error", request=error_response.request, response=error_response
        )

        await base_manager.commit_uncommitted(task, conn=mock_conn)

        assert task.status == "failed"

    @pytest.mark.asyncio
    async def test_commit_uncommitted_move(self, base_manager, mock_conn):
        task = ChangeTask(change=MoveRequest(["href1"], "dest"), status="uncommitted")
        base_manager.add_task(task)

        mock_conn.POST.side_effect = [
            httpx.Response(
                202,
                content=b'{"location": "/location/123", "id": "abc", "status": "started", "maxInterval": 10}',
                request=httpx.Request("POST", "url"),
            )
        ]

        await base_manager.commit_uncommitted(task, conn=mock_conn)

        assert task.status == "submitted"
        assert base_manager.task_statuslocation[task.id] == "/location/123"

    @pytest.mark.asyncio
    async def test_commit_uncommitted_upload(self, base_manager, mock_conn):
        task = ChangeTask(
            change=UploadRequest(memoryview(b"123"), "dest", "fn", 3, [], []),
            status="uncommitted",
        )
        base_manager.add_task(task)

        mock_conn.POST.side_effect = [
            httpx.Response(
                202,
                content=b'{"id": "upl1", "numChunks": 1, "chunkSize": 100}',
                request=httpx.Request("POST", "url"),
            ),
            httpx.Response(204, request=httpx.Request("POST", "url")),
        ]

        await base_manager.commit_uncommitted(task, conn=mock_conn)

        assert task.status == "submitted"
        assert (
            base_manager.task_statuslocation[task.id]
            == "/fotoweb/api/uploads/upl1/status"
        )
