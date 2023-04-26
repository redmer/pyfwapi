import time
from typing import Iterator

import requests
from fastapi import HTTPException, status

from ..config import PUBLIC_DOCTYPES, PUBLIC_METADATA_KEY, PUBLIC_METADATA_VALUE
from . import Asset, api
from .exports import export_locations
from .log import FotowareLog

ASSET_DOCTYPE = ["image", "movie", "audio", "document", "graphic", "generic"]
NUM_CONNECTION_RETRIES = 5


def is_public(asset: Asset):
    return asset.get("doctype") in PUBLIC_DOCTYPES or (
        asset.get("metadata", {}).get(PUBLIC_METADATA_KEY, {}).get("value")
        == PUBLIC_METADATA_VALUE
    )


def stream_asset(asset_href: str) -> Iterator[bytes]:
    href = export_locations(asset_href)
    return retrying_get_binary(href["doubleResolution"])


def retrying_get_binary(href: str) -> Iterator[bytes]:
    """Try and retry to get the binary stream of a file"""
    retries = int(NUM_CONNECTION_RETRIES)
    while True:
        asset = requests.get(href, headers=api.auth_header(), stream=True)
        if asset.status_code == 200:
            return asset.iter_content()
        if retries == 0:
            FotowareLog.error(
                f"Download '{href}' failed ({asset.status_code}) after {NUM_CONNECTION_RETRIES}"
            )
            raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT)

        retries -= 1
        time.sleep(0.5)


def unstream(stream: Iterator[bytes]) -> bytes:
    return b"".join(stream) or b""


# def get_contents(asset: fotoware_api.Asset) -> bytes:
#     """Get file contents of a Fotoware asset"""

#     return unstream(stream(asset))


# def stream(asset: fotoware_api.Asset) -> Iterator[bytes]:
#     """Returns the most appropriate filestream"""

#     # -> if the asset is an image, the exports API is the best (and cached) option
#     if can_be_exported(asset):
#         return stream_asset(asset["href"])

#     # -> Otherwise, the original renditions should be requested
#     if has_renditions(asset):
#         orig = original_rendition(asset["renditions"])
#         return stream_rendition(orig)

#     logging.error(f"No export nor rendition found for asset '{asset['href']}'")
#     raise HTTPException(status.HTTP_404_NOT_FOUND)
