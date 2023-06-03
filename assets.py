from asyncio import sleep

import aiohttp
from fastapi import HTTPException, status

from ..config import PUBLIC_DOCTYPES, PUBLIC_METADATA_KEY, PUBLIC_METADATA_VALUE
from . import api
from .apitypes import Asset
from .log import FotowareLog

ASSET_DOCTYPE = ["image", "movie", "audio", "document", "graphic", "generic"]
NUM_CONNECTION_RETRIES = 10


def is_public(asset: Asset):
    return asset.get("doctype") in PUBLIC_DOCTYPES or (
        asset.get("metadata", {}).get(PUBLIC_METADATA_KEY, {}).get("value")
        == PUBLIC_METADATA_VALUE
    )


def builtin_field(asset: Asset, name: str):
    for field in asset["builtinFields"]:
        if field["field"] == name:
            return field["value"]
    return None


def metadata_field(asset: Asset, name: str):
    for k, v in asset["metadata"].items():
        if k == name:
            return v["value"]
    return None


async def retrying_response(href: str) -> aiohttp.ClientResponse:
    """Try and retry to get the binary stream of a file"""
    retries = int(NUM_CONNECTION_RETRIES)
    while retries > 0:
        asset = await api.SESSION.get(href, headers=await api.auth_header())
        if asset.status == 200:
            return asset

        retries -= 1
        await sleep(0.5)

    FotowareLog.error(f"Download '{href}' failed after {NUM_CONNECTION_RETRIES}")
    raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT)
