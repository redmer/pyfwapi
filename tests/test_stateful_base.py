import asyncio
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

    @pytest.mark.asyncio
    async def test_commit_only_commits_uncommitted(self, base_manager, mock_conn):
        """commit() skips tasks that are not 'uncommitted'."""
        pending = ChangeTask(
            change=MetadataRequest("href", {1: {"value": "v"}}), status="uncommitted"
        )
        done = ChangeTask(
            change=MetadataRequest("href", {1: {"value": "v"}}), status="done"
        )
        base_manager.add_task(pending)
        base_manager.add_task(done)

        mock_conn.PATCH.return_value = httpx.Response(200)

        await base_manager.commit(conn=mock_conn)

        assert pending.status == "done"
        mock_conn.PATCH.assert_awaited_once()  # 'done' task was not re-committed

    @pytest.mark.asyncio
    async def test_commit_bounded_by_max_concurrent_tasks(self, mock_conn):
        """commit() runs tasks in parallel, bounded by max_concurrent_tasks."""
        manager = BaseChangeManager(max_concurrent_tasks=2)
        mock_conn.PATCH.return_value = httpx.Response(200)

        in_flight = 0
        max_in_flight = 0

        original = manager.commit_uncommitted

        async def counting_commit(ch, *, conn):
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.01)
            try:
                await original(ch, conn=conn)
            finally:
                in_flight -= 1

        manager.commit_uncommitted = counting_commit

        tasks = [
            ChangeTask(
                change=MetadataRequest(f"href{i}", {1: {"value": "v"}}),
                status="uncommitted",
            )
            for i in range(5)
        ]
        for task in tasks:
            manager.add_task(task)

        await manager.commit(conn=mock_conn)

        assert max_in_flight == 2  # parallelism happened but was bounded
        assert all(t.status == "done" for t in tasks)

    @pytest.mark.asyncio
    async def test_check_submitted_move_done(self, base_manager, mock_conn):
        task = ChangeTask(change=MoveRequest(["href1"], "dest"), status="submitted")
        base_manager.add_task(task)
        base_manager.task_statuslocation[task.id] = "/location/123"

        mock_conn.GET.return_value = httpx.Response(
            200,
            content=(
                b'{"job": {"status": "done", "updates": 0, "result": []},'
                b' "task": {"status": "done", "type": "move", "created": "2024-01-01",'
                b' "modified": "2024-01-01", "id": "abc"}}'
            ),
            request=httpx.Request("GET", "url"),
        )

        await base_manager.check_submitted(conn=mock_conn)

        assert task.status == "done"

    @pytest.mark.asyncio
    async def test_check_submitted_move_failed(self, base_manager, mock_conn):
        task = ChangeTask(change=MoveRequest(["href1"], "dest"), status="submitted")
        base_manager.add_task(task)
        base_manager.task_statuslocation[task.id] = "/location/123"

        mock_conn.GET.return_value = httpx.Response(
            200,
            content=(
                b'{"job": {"status": "failed", "updates": 0, "result": []},'
                b' "task": {"status": "failed", "type": "move", "created": "2024-01-01",'
                b' "modified": "2024-01-01", "id": "abc"}}'
            ),
            request=httpx.Request("GET", "url"),
        )

        await base_manager.check_submitted(conn=mock_conn)

        assert task.status == "failed"

    @pytest.mark.asyncio
    async def test_check_submitted_upload_done(self, base_manager, mock_conn):
        task = ChangeTask(
            change=UploadRequest(memoryview(b"x"), "dest", "fn", 1, [], []),
            status="submitted",
        )
        base_manager.add_task(task)
        base_manager.task_statuslocation[task.id] = "/fotoweb/api/uploads/upl1/status"

        mock_conn.GET.return_value = httpx.Response(
            200,
            content=(
                b'{"status": "done",'
                b' "result": {"assetUrl": "/a", "assetDetails": "d"},'
                b' "error": {"value": "v", "message": "m"}}'
            ),
            request=httpx.Request("GET", "url"),
        )

        await base_manager.check_submitted(conn=mock_conn)

        assert task.status == "done"

    @pytest.mark.asyncio
    async def test_check_submitted_skips_without_location(
        self, base_manager, mock_conn
    ):
        """Submitted tasks with no stored status location are skipped."""
        task = ChangeTask(change=MoveRequest(["href1"], "dest"), status="submitted")
        base_manager.add_task(task)  # no entry in task_statuslocation

        await base_manager.check_submitted(conn=mock_conn)

        mock_conn.GET.assert_not_awaited()
        assert task.status == "submitted"

    @pytest.mark.asyncio
    async def test_check_submitted_bounded_and_parallel(self, mock_conn):
        """check_submitted() polls in parallel, bounded by max_concurrent_tasks."""
        manager = BaseChangeManager(max_concurrent_tasks=2)
        response = httpx.Response(
            200,
            content=(
                b'{"job": {"status": "done", "updates": 0, "result": []},'
                b' "task": {"status": "done", "type": "move", "created": "2024-01-01",'
                b' "modified": "2024-01-01", "id": "abc"}}'
            ),
            request=httpx.Request("GET", "url"),
        )

        in_flight = 0
        max_in_flight = 0

        async def counting_get(*args, **kwargs):
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1
            return response

        mock_conn.GET.side_effect = counting_get

        tasks = [
            ChangeTask(change=MoveRequest([f"href{i}"], "dest"), status="submitted")
            for i in range(5)
        ]
        for task in tasks:
            manager.add_task(task)
            manager.task_statuslocation[task.id] = "/location/x"

        await manager.check_submitted(conn=mock_conn)

        assert max_in_flight == 2
        assert all(t.status == "done" for t in tasks)

    @pytest.mark.asyncio
    async def test_upload_final_partial_chunk_uses_remaining_bytes(
        self, base_manager, mock_conn
    ):
        """The final chunk must be sized to the remainder, not the full
        chunkSize (regression test for the chunk size fix)."""
        content = b"x" * 250  # 3 chunks of size 100: 100, 100, 50
        task = ChangeTask(
            change=UploadRequest(memoryview(content), "dest", "fn", 250, [], []),
            status="uncommitted",
        )
        base_manager.add_task(task)

        mock_conn.POST.side_effect = [
            httpx.Response(
                202,
                content=b'{"id": "upl1", "numChunks": 3, "chunkSize": 100}',
                request=httpx.Request("POST", "url"),
            ),
            httpx.Response(204, request=httpx.Request("POST", "url")),
            httpx.Response(204, request=httpx.Request("POST", "url")),
            httpx.Response(204, request=httpx.Request("POST", "url")),
        ]

        await base_manager.commit_uncommitted(task, conn=mock_conn)

        assert task.status == "submitted"

        chunk_calls = mock_conn.POST.await_args_list[1:]
        assert len(chunk_calls) == 3

        by_url = {c.args[0]: c.kwargs["files"]["chunk"][1] for c in chunk_calls}
        assert len(by_url["/fotoweb/api/uploads/upl1/chunks/0"]) == 100
        assert len(by_url["/fotoweb/api/uploads/upl1/chunks/1"]) == 100
        assert len(by_url["/fotoweb/api/uploads/upl1/chunks/2"]) == 50  # remainder
        assert by_url["/fotoweb/api/uploads/upl1/chunks/2"] == content[200:250]

    @pytest.mark.asyncio
    async def test_upload_chunks_bounded_by_max_concurrent_chunks(self, mock_conn):
        """Chunk uploads run in parallel, bounded by max_concurrent_chunks."""
        manager = BaseChangeManager(max_concurrent_chunks=2)
        content = b"x" * 400  # 4 chunks of 100
        task = ChangeTask(
            change=UploadRequest(memoryview(content), "dest", "fn", 400, [], []),
            status="uncommitted",
        )
        manager.add_task(task)

        in_flight = 0
        max_in_flight = 0

        info_response = httpx.Response(
            202,
            content=b'{"id": "upl1", "numChunks": 4, "chunkSize": 100}',
            request=httpx.Request("POST", "url"),
        )
        chunk_response = httpx.Response(204, request=httpx.Request("POST", "url"))

        async def counting_post(*args, **kwargs):
            nonlocal in_flight, max_in_flight
            if "/chunks/" not in args[0]:
                return info_response
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1
            return chunk_response

        mock_conn.POST.side_effect = counting_post

        await manager.commit_uncommitted(task, conn=mock_conn)

        assert task.status == "submitted"
        assert max_in_flight == 2
