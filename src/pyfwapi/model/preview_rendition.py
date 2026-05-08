from pyfwapi.model.basemodel import APIResponse


class WidthHeightTrait(APIResponse):
    """Traits in common between Previews and Rendition types"""

    width: int = -1
    height: int = -1


CommonTrait = WidthHeightTrait  # API stability export


class PreviewTrait(WidthHeightTrait):
    """The traits of an asset preview"""

    square: bool
    size: int = -1


class RenditionTrait(WidthHeightTrait):
    """Traits of a rendition type of an asset"""

    original: bool | None
    profile: str | None


class AssetPreview(PreviewTrait):
    href: str


class AssetRendition(RenditionTrait):
    href: str

    display_name: str
    description: str | None
    default: bool


class QuickRendition(PreviewTrait):
    href: str

    name: str
