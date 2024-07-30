import typing as t
from datetime import datetime

from pyfwapi.model.basemodel import APIResponse
from pyfwapi.model.preview_rendition import AssetPreview, AssetRendition

type BuiltinFieldName = t.Literal[
    "title", "description", "tags", "notes", "status", "rating"
]
type MetadataFieldType = str | bool | list[str]
type ColorSpaceValues = t.Literal["grayscale", "rgb", "cmyk", "unknown"]
type ImageOrientationValues = t.Literal["portrait", "landscape"]
type AssetTypeValues = t.Literal[
    "image", "movie", "audio", "document", "graphic", "generic"
]


class BuiltinField(APIResponse):
    """A built-in metadata field (title, description, etc.)"""

    field: BuiltinFieldName
    required: bool
    value: MetadataFieldType | None


class MetadataField(APIResponse):
    """Any metadata field (that is, not built-in)"""

    value: MetadataFieldType


class ImageAttributes(APIResponse):
    pixelwidth: int
    pixelheight: int
    resolution: float
    flipmirror: int
    rotation: int
    colorspace: ColorSpaceValues


class Attributes(APIResponse):
    imageattributes: ImageAttributes | None = None


class Asset(APIResponse):
    """A file in the asset library, like a photo, video, ZIP file, etc."""

    href: str
    physicalFileId: str
    linkstance: str

    filename: str
    filesize: int

    doctype: AssetTypeValues
    created: datetime | None
    modified: datetime | None
    archiveId: int
    archiveHREF: str

    builtinFields: list[BuiltinField]
    metadata: dict[int, MetadataField]
    attributes: Attributes | None = None

    previews: list[AssetPreview] | None
    previewToken: str
    renditions: list[AssetRendition] | None
    quickRenditions: list[AssetRendition] | None

    archiveId: int

    def get_builtin[T: t.Any](
        self, key: BuiltinFieldName, /, default: T = None
    ) -> MetadataFieldType | None | T:
        """Get a metadata value, from a limited list of builtin fields"""
        for field in self.builtinFields:
            if field.field == key:
                return field.value
        return default

    def get_metadata[T: t.Any](
        self, key: int, /, default: T = None
    ) -> MetadataFieldType | None | T:
        """Get a metadata value, from a customizable list of numbered metadata fields"""
        return self.metadata[key].value

    def find_rendition(
        self,
        *,
        original: bool | None = None,
        size: int = 0,
        width: int = 0,
        height: int = 0,
        profile: str | None = None,
    ) -> AssetRendition | None:
        """The first rendition that qualifies with the specified constraints"""
        if self.renditions is None:
            return None

        qualified = filter(lambda r: True, self.renditions)

        if profile is not None:
            qualified = filter(lambda i: i.profile == profile, qualified)
        if original is not None:
            qualified = filter(lambda i: original == i.original, qualified)

        # A SIZE equals the length of the longest side. Matching a minimum size, the shortest
        # (= min()) side should determine match.
        qualified = filter(lambda i: size <= min([i.height, i.width]), qualified)
        qualified = filter(lambda i: width <= i.width, qualified)
        qualified = filter(lambda i: height <= i.height, qualified)

        return next(qualified, None)  # next = first = qualified[0]

    def find_preview(
        self,
        *,
        size: int = 0,
        width: int = 0,
        height: int = 0,
        square: bool | None = None,
    ) -> AssetPreview | None:
        """Find the first preview URL that qualifies with the specified constraints"""
        if self.previews is None:
            return None

        qualified = filter(lambda r: True, self.previews)

        qualified = filter(lambda i: size <= i.size, qualified)
        qualified = filter(lambda i: width <= i.width, qualified)
        qualified = filter(lambda i: height <= i.height, qualified)
        if square is not None:
            qualified = filter(lambda i: i.square is square, qualified)

        return next(qualified)  # next = first = qualified[0]


class ImageExport(APIResponse):
    """The result dict of an exported image"""

    normal: str
    doubleResolution: str
    highCompression: str
