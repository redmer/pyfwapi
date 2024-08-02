import typing as t

from pydantic import Field

from pyfwapi.model.basemodel import APIResponse


class HasHref(t.TypedDict):
    href: str


class _FieldValue(t.TypedDict):
    field: int
    value: str


MetadataEditRequest = t.TypedDict(
    "MetadataEditRequest",
    {
        "assets": list[HasHref],
        "job-metadata": list[_FieldValue],
    },
)


MoveRequest = t.TypedDict(
    "MoveRequest",
    {
        "assets": list[HasHref],
        "job-destination": str,
    },
)


class BackgroundTaskResponse(APIResponse):
    maxInterval: int
    location: str
    status: str


class TaskStatusJobResult(APIResponse):
    href: str
    done: bool
    result_href: str = Field(alias="result-href")
    result_collection_created: bool = Field(alias="result-collection-created")
    result_collection_href: str = Field(alias="result-collection-href")
    changed_thumbnail_fields: list[str] = Field(alias="changed-thumbnailFields")
    original_removed: bool = Field(alias="original-removed")
    result_filename: str = Field(alias="result-filename")


class TaskStatusJob(APIResponse):
    status: t.Literal["pending", "inProgress", "done", "failed"]
    updates: int
    result: list[TaskStatusJobResult]


class TaskStatusTask(APIResponse):
    status: t.Literal["pending", "inProgress", "done", "failed"]
    type: str
    created: str
    modified: str
    id: str


class TaskStatus(APIResponse):
    job: TaskStatusJob
    task: TaskStatusTask
