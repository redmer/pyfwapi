from datetime import datetime

from pyfwapi.model.basemodel import APIResponse


class Archive(APIResponse):
    name: str
    description: str | None
    href: str
    data: str
    id: str | None
    type: str

    created: datetime | None
    modified: datetime | None

    searchURL: str | None
    originalURL: str | None

    assetCount: int = -1
