from pyfwapi.model.basemodel import APIResponse


class CommonTrait(APIResponse):
    """Traits in common between Previews and Rendition types"""

    width: int = -1
    height: int = -1


class PreviewTrait(CommonTrait):
    """The traits of an asset preview"""

    square: bool
    size: int = -1


class RenditionTrait(CommonTrait):
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
