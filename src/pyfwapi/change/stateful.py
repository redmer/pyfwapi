import asyncio
import dataclasses
import typing as t
from dataclasses import dataclass, field
from uuid import uuid4

import httpxyz as httpx

from pyfwapi.apiconnection import APIConnection
from pyfwapi.errors import UploadException
from pyfwapi.log import pyfwapiLog
from pyfwapi.model.asset import MetadataFieldType
from pyfwapi.model.background_tasks import BackgroundTaskResponse, TaskStatus
from pyfwapi.model.upload_request import BatchUploadInfo, BatchUploadStatus


class MetadataPatch(t.TypedDict):
    id: int
    action: t.Literal["add", "append", "prepend", "erase"]
    value: str | list[str]


class MetadataAttributesPatch(t.TypedDict):
    key: t.Literal["mt"]
    value: str


class ValueMetadataField(t.TypedDict):
    value: MetadataFieldType


@dataclass(frozen=True)
class MetadataRequest:
    asset_href: str
    new_metadata: dict[int, ValueMetadataField]


@dataclass(frozen=True)
class UploadRequest:
    contents: memoryview
    destination: str
    filename: str
    filesize: int
    fields: list[MetadataPatch]
    attributes: list[MetadataAttributesPatch]


@dataclass(frozen=True)
class MoveRequest:
    asset_hrefs: list[str]
    destination: str


@dataclass
class ChangeTask:
    change: MoveRequest | UploadRequest | MetadataRequest
    status: t.Literal["uncommitted", "submitted", "done", "failed"] = "uncommitted"
    id: bytes = field(default_factory=lambda: uuid4().bytes)

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f"Change(type={type(self.change)}, status={self.status} [id={self.id}])"


class BaseChangeManager:
    """
    The class that keeps track of to-be uploaded tasks, executes uploads and web
    requests, and can keep track of background tasks.

    Consider using ChangeManager for a higher-level API.

    Args:
        max_concurrent_tasks: how many independent changes (uploads, moves,
            metadata patches) may be committed in parallel.
        max_concurrent_chunks: how many chunks of a single upload may be in
            flight at the same time. The FotoWare Upload API explicitly allows
            chunks to be uploaded in any order and in parallel.
    """

    def __init__(
        self, *, max_concurrent_tasks: int = 4, max_concurrent_chunks: int = 4
    ) -> None:
        self.tasks: dict[bytes, ChangeTask] = dict()
        self.task_statuslocation: dict[bytes, str] = dict()
        self._task_semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._chunk_semaphore = asyncio.Semaphore(max_concurrent_chunks)

    def add_task(self, task: ChangeTask):
        self.tasks[task.id] = task

    async def commit(self, *, conn: APIConnection, await_done: bool = True):
        """Commit changes ready to commit.

        Independent tasks are committed in parallel, bounded by
        ``max_concurrent_tasks``. All requests still pass through the
        connection-level rate limiter.
        """

        async def _commit(task: ChangeTask):
            async with self._task_semaphore:
                await self.commit_uncommitted(task, conn=conn)

        await asyncio.gather(
            *(
                _commit(task)
                for task in self.tasks.values()
                if task.status == "uncommitted"
            )
        )

    async def commit_uncommitted(self, ch: ChangeTask, *, conn: APIConnection):
        """Commit a single uncommitted ChangeTask."""
        if isinstance(ch.change, MetadataRequest):
            success = await self.patch_metadata(ch.change, conn=conn)
            if success:
                ch.status = "done"
                return
            ch.status = "failed"

        elif isinstance(ch.change, MoveRequest):
            task = await self.move_asset(ch.change, conn=conn)
            ch.status = "submitted"
            self.task_statuslocation[ch.id] = task.location

        elif isinstance(ch.change, UploadRequest):
            task = await self.upload_asset(ch.change, conn=conn)
            ch.status = "submitted"
            self.task_statuslocation[ch.id] = f"/fotoweb/api/uploads/{task.id}/status"

    async def check_submitted(self, *, conn: APIConnection):
        """Check the processing status of backgrounded tasks, like moves and uploads.

        All submitted tasks are polled in parallel, bounded by
        ``max_concurrent_tasks``.
        """

        async def _check(task: ChangeTask):
            location = self.task_statuslocation.get(task.id)
            if location is None:
                return

            if isinstance(task.change, MoveRequest):
                r = await conn.GET(location)
                info = TaskStatus.model_validate_json(r.content)
                match info.task.status:
                    case "done":
                        task.status = "done"
                    case "failed":
                        task.status = "failed"
                        pyfwapiLog.warn(f"Move failed (fn:{task.change.asset_hrefs})")

            if isinstance(task.change, UploadRequest):
                r = await conn.GET(location)
                info = BatchUploadStatus.model_validate_json(r.content)
                match info.status:
                    case "done":
                        task.status = "done"
                    case "failed":
                        task.status = "failed"
                        pyfwapiLog.warn(f"Upload failed (fn:{task.change.filename})")

        async def _check_bounded(task: ChangeTask):
            async with self._task_semaphore:
                await _check(task)

        await asyncio.gather(
            *(
                _check_bounded(task)
                for task in self.tasks.values()
                if task.status == "submitted"
            )
        )

    async def patch_metadata(
        self, item: MetadataRequest, *, conn: APIConnection
    ) -> bool:
        """Handle a single AssetMetadataChange. Returns False upon error."""

        try:
            await conn.PATCH(
                item.asset_href,
                headers={"Content-Type": "application/vnd.fotoware.assetupdate+json"},
                json={"metadata": dataclasses.asdict(item)["new_metadata"]},
            )
        except httpx.HTTPStatusError as err:
            pyfwapiLog.warning(f"{item} failed, because: {err}")
            return False
        else:
            return True

    async def move_asset(
        self, item: MoveRequest, *, conn: APIConnection
    ) -> BackgroundTaskResponse:
        """Handle a single MoveRequest."""
        assets = list(({"href": href} for href in item.asset_hrefs))
        d = await conn.POST(
            "/fotoweb/me/background-tasks/",
            headers={
                "Content-Type": "application/vnd.fotoware.move-request+json",
            },
            json={
                "assets": assets,
                "job-destination": item.destination,
            },
        )

        return BackgroundTaskResponse.model_validate_json(d.content)

    async def upload_asset(self, item: UploadRequest, *, conn: APIConnection):
        """Handle a single UploadRequest"""
        # submit upload request...
        r = await conn.POST(
            "/fotoweb/api/uploads",
            headers={"Content-Type": "application/json"},
            json={
                "destination": item.destination,
                "filename": item.filename,
                "hasXmp": False,
                "fileSize": item.filesize,
                "checkoutId": None,
                "metadata": {
                    "fields": item.fields,
                    "attributes": item.attributes,
                },
                "comment": None,
            },
        )

        upload_info = BatchUploadInfo.model_validate_json(r.content)

        # Chunks may be uploaded in any order and in parallel (per the FotoWare
        # Upload API docs). Concurrency is bounded so we stay well within
        # server-side rate limits; every request also passes through the
        # connection-level rate limiter.
        async def _upload_chunk(i: int):
            async with self._chunk_semaphore:
                await self._upload_asset_chunk(i, upload_info, item, conn=conn)

        await asyncio.gather(*(_upload_chunk(i) for i in range(upload_info.numChunks)))

        return upload_info

    async def _upload_asset_chunk(
        self,
        i: int,
        upload_info: BatchUploadInfo,
        item: UploadRequest,
        *,
        conn: APIConnection,
    ):
        """Upload a chunk of a new asset."""
        chunk_offset = i * upload_info.chunkSize
        chunk_size = min(upload_info.chunkSize, item.filesize - chunk_offset)
        chunk_end = chunk_offset + chunk_size

        bytes_part = item.contents[chunk_offset:chunk_end]

        resp = await conn.POST(
            f"/fotoweb/api/uploads/{upload_info.id}/chunks/{i}",
            files={
                "chunk": ("chunk", bytes_part.tobytes(), "application/octet-stream")
            },
        )

        if resp.status_code != 204:
            raise UploadException(resp.text)
