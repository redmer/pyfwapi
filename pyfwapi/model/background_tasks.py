import typing as t

from pydantic import Field

from pyfwapi.model.basemodel import APIResponse


class BackgroundRequestResp(APIResponse):
    maxInterval: int
    location: str
    status: str


class BackgroundTaskJobInfoResult(APIResponse):
    href: str
    done: bool
    result_href: str = Field(alias="result-href")
    result_collection_created: bool = Field(alias="result-collection-created")
    result_collection_href: str = Field(alias="result-collection-href")
    changed_thumbnail_fields: list[str] = Field(alias="changed-thumbnailFields")
    original_removed: bool = Field(alias="original-removed")
    result_filename: str = Field(alias="result-filename")


class BackgroundTaskJobInfo(APIResponse):
    status: t.Literal["pending", "inProgress", "done", "failed"]
    updates: int
    result: list[BackgroundTaskJobInfoResult]


class BackgroundTaskTaskInfo(APIResponse):
    status: t.Literal["pending", "inProgress", "done", "failed"]
    type: str
    created: str
    modified: str
    id: str


class BackgroundTaskResp(APIResponse):
    job: BackgroundTaskJobInfo
    task: BackgroundTaskTaskInfo
