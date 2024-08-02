import dataclasses
import typing as t
from dataclasses import dataclass, field
from uuid import uuid4

import aiohttp
from aiohttp import BytesPayload
from httpx import HTTPStatusError

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
    """

    def __init__(self) -> None:
        self.tasks: dict[bytes, ChangeTask] = dict()
        self.task_statuslocation: dict[bytes, str] = dict()

    def add_task(self, task: ChangeTask):
        self.tasks[task.id] = task

    async def commit(self, *, conn: APIConnection, await_done: bool = True):
        """Commit changes ready to commit."""
        for task in self.tasks.values():
            if task.status != "uncommitted":
                continue
            await self.commit_uncommitted(task, conn=conn)

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
        """Check the processing status of backgrounded tasks, like moves and uploads."""
        for task in self.tasks.values():
            if task.status != "submitted":
                continue
            location = self.task_statuslocation.get(task.id)
            if location is None:
                continue

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

    async def patch_metadata(
        self, item: MetadataRequest, *, conn: APIConnection
    ) -> bool:
        """Handle a single AssetMetadataChange. Returns False upon error."""

        try:
            await conn.PATCH(
                item.asset_href,
                headers={"Content-Type": "application/vnd.fotoware.assetupdate+json"},
                data={"metadata": dataclasses.asdict(item)["new_metadata"]},
            )
        except HTTPStatusError as err:
            pyfwapiLog.warning(f"{item} failed, because:", err)
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
            data={
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
            data={
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

        for i in range(upload_info.numChunks):
            await self._upload_asset_chunk(i, upload_info, item, conn=conn)

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
        chunk_size = min([upload_info.chunkSize, item.filesize])
        chunk_end = chunk_offset + chunk_size

        with aiohttp.MultipartWriter("form-data") as mp:
            bytes_part = item.contents[chunk_offset:chunk_end]
            part = mp.append_payload(
                BytesPayload(
                    bytes_part,
                    content_type="application/octet-stream",
                )
            )
            part.set_content_disposition("form-data", name="chunk", filename="chunk")

            resp = await conn.POST(
                f"/fotoweb/api/uploads/{upload_info.id}/chunks/{i}",
                data=mp,
                headers=mp.headers,
            )

            if resp.status_code != 204:
                raise UploadException(resp.text)
