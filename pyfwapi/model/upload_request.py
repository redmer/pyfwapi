import typing as t

from pyfwapi.model.basemodel import APIResponse


class BatchUploadInfo(APIResponse):
    id: str
    chunkSize: int
    numChunks: int


class BatchUploadStatusError(APIResponse):
    value: str
    message: str


class BatchUploadStatusResult(APIResponse):
    assetUrl: str
    assetDetails: str


class BatchUploadStatus(APIResponse):
    status: t.Literal["awaitingData", "pending", "inProgess", "done", "failed"]
    result: BatchUploadStatusResult
    error: BatchUploadStatusError
