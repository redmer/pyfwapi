from pydantic import field_validator
from pydantic_core.core_schema import FieldValidationInfo

from pyfwapi.model.basemodel import APIResponse


class CommonTrait(APIResponse):
    """Traits in common between Previews and Rendition types"""

    width: int = -1
    height: int = -1
    size: int = -1

    @field_validator("size", mode="before")
    @classmethod
    def size_is_max_width_heigh(cls, v, info: FieldValidationInfo):
        if v:
            return v
        return max(int(info.data["width"]), int(info.data["height"]))


class PreviewTrait(CommonTrait):
    """The traits of an asset preview"""

    square: bool


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
