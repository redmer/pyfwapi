from typing import Literal, TypedDict


class PreviewTrait(TypedDict):
    """The traits of an asset preview"""

    height: int
    size: int
    square: bool
    width: int


class RenditionTrait(TypedDict):
    """Traits of a rendition type of an asset"""

    height: int
    original: bool
    profile: str
    width: int


def traitkey(trait: TypedDict) -> str:
    if trait.get("original") is True:
        return "original"  # overrides all other
    return ":".join(
        f"{k}:{v}" for k, v in sorted((k, v) for k, v in trait.items() if v is not None)
    )


class AssetPreview(PreviewTrait):
    href: str


class AssetRendition(RenditionTrait):
    href: str


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
