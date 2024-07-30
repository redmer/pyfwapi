from pyfwapi.model.basemodel import APIResponse


class FotowareUploadRequest(APIResponse):
    upload_id: str
    chunkSize: int
    numChunks: int
