import aiohttp
from fastapi import HTTPException, status

from ..config import FOTOWARE_HOST
from . import api, apitypes
from .log import FotowareLog


def has_previews(asset: apitypes.Asset) -> bool:
    """This asset has pre-rendered previews"""
    return "previews" in asset


def find_preview(
    data: list[apitypes.AssetPreview],
    *,
    size: int = 0,
    width: int = 0,
    height: int = 0,
    square: bool | None = None,
) -> apitypes.AssetPreview | None:
    """Find the first preview URL that qualifies with the specified constraints"""
    qualified = filter(lambda i: size <= i["size"], data)
    qualified = filter(lambda i: width <= i["width"], qualified)
    qualified = filter(lambda i: height <= i["height"], qualified)
    if square is not None:
        qualified = filter(lambda i: i["square"] is square, qualified)

    return next(qualified)  # next = first = qualified[0]


async def preview_response(
    preview: apitypes.AssetPreview, previewToken: str
) -> aiohttp.ClientResponse:
    """Return the preview image binary. PreviewToken is a property of the asset."""

    resp = await api.SESSION.get(
        FOTOWARE_HOST + preview["href"],
        headers={"Authorization": f"Bearer {previewToken}"},
    )

    if not resp.ok:
        reason = await resp.text()
        FotowareLog.error(f"Rendition request '{preview['href']}' failed ({reason})")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=reason)

    return resp
