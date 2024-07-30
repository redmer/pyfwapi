from pyfwapi.model.basemodel import APIResponse
from pyfwapi.model.paged import Paged


class Collection(APIResponse):
    id: str | None
    name: str
    description: str | None
    href: str
    data: str
    type: str

    created: str | None = None
    modified: str | None = None
    archived: str | None = None

    searchURL: str
    originalURL: str

    isSearchable: bool
    permissions: list[str]
    canMoveTo: bool
    canUploadTo: bool

    assetCount: int = -1
    # ancestors: list["Collection"] | None = None
    # props: dict[str, t.Any]
    # assets: Paged[Asset] | None = None
    # children: Paged["Collection"] | None = None


class CollectionList(Paged[Collection]):
    searchURL: str
