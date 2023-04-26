from typing import Iterator

import requests
from fastapi import HTTPException, status

from . import api


def has_previews(asset: api.Asset) -> bool:
    """This asset has pre-rendered previews"""
    return "previews" in asset


def find_preview(
    data: list[api.AssetPreview],
    *,
    size: int = 0,
    width: int = 0,
    height: int = 0,
    square: bool | None = None,
) -> api.AssetPreview | None:
    """Find the first preview URL that qualifies with the specified constraints"""
    qualified = filter(lambda i: size <= i["size"], data)
    qualified = filter(lambda i: width <= i["width"], qualified)
    qualified = filter(lambda i: height <= i["height"], qualified)
    if square is not None:
        qualified = filter(lambda i: i["square"] is square, qualified)

    return next(qualified)  # next = first = qualified[0]


def stream_preview(preview: api.AssetPreview, previewToken: str) -> Iterator[bytes]:
    """Return the preview image binary. PreviewToken is a property of the asset."""
    content = requests.get(
        api.FOTOWARE_HOST + preview["href"],
        headers={"Authorization": f"Bearer {previewToken}"},
        stream=True,
    )

    if not content.ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return content.iter_content(None)
