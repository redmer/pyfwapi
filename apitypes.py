from typing import Literal, TypedDict


class AssetPreview(TypedDict):
    """The traits of an asset preview"""

    height: int
    href: str
    size: int
    square: bool
    width: int


class AssetRendition(TypedDict):
    """Traits of a rendition type of an asset"""

    height: int
    href: str
    original: bool
    profile: str
    width: int


class BuiltinField(TypedDict):
    """A built-in metadata field (title, description, etc.)"""

    field: str
    required: bool
    value: str | int | bool | list[str]


class MetadataField(TypedDict):
    """Any metadata field (that is, not built-in)"""

    value: str | int | bool | list[str]


class Asset(TypedDict):
    """An asset representation in Fotoware"""

    created: str
    doctype: Literal["image", "movie", "audio", "document", "graphic", "generic"]
    filename: str
    filesize: int
    href: str
    builtinFields: list[BuiltinField]
    metadata: dict[str, MetadataField]
    modified: str
    physicalFileId: str
    previews: list[AssetPreview]
    previewToken: str
    renditions: list[AssetRendition]


class ImageExport(TypedDict):
    """The result dict of an exported image"""

    normal: str
    doubleResolution: str
    highCompression: str
