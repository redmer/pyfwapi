from contextlib import asynccontextmanager
import json
from datetime import datetime, timedelta
from typing import Tuple

from aiohttp import ClientSession
from aiohttp_client_cache.backends.redis import RedisBackend
from aiohttp_client_cache.session import CachedSession
from fastapi import FastAPI, HTTPException, status

from ..config import (
    FOTOWARE_CLIENT_ID,
    FOTOWARE_CLIENT_SECRET,
    FOTOWARE_HOST,
    REDIS_HOST,
)
from .log import FotowareLog

CACHE = RedisBackend(address=f"redis://{REDIS_HOST}", expire_after=timedelta(days=1))
SESSION: ClientSession = CachedSession(cache=CACHE)


FOTOWARE_ACCESS_TOKEN: str | None = None
FW_ACCESS_TOKEN_EXP: datetime = datetime.utcnow()


@asynccontextmanager
async def api_lifespan(app: FastAPI):
    yield
    await SESSION.close()


async def access_token() -> str:
    """Get the OAuth2 Access Token from the environment variables CLIENT_ID and CLIENT_SECRET"""

    global FOTOWARE_ACCESS_TOKEN
    global FW_ACCESS_TOKEN_EXP

    async def request_new_access_token() -> Tuple[str, float]:
        FotowareLog.debug("Requesting NEW access token")
        r = await SESSION.post(
            # r = await fwclient.post(
            FOTOWARE_HOST + "/fotoweb/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": FOTOWARE_CLIENT_ID,
                "client_secret": FOTOWARE_CLIENT_SECRET,
            },
            allow_redirects=True,
            headers={"Accept": "application/json"},
        )
        response = await r.json()
        return response["access_token"], response["expires_in"]

    if FW_ACCESS_TOKEN_EXP <= datetime.utcnow():  # invalidate if expired
        FOTOWARE_ACCESS_TOKEN = None

    if FOTOWARE_ACCESS_TOKEN is None:
        FOTOWARE_ACCESS_TOKEN, exp_in_seconds = await request_new_access_token()
        FW_ACCESS_TOKEN_EXP = datetime.utcnow() + timedelta(seconds=exp_in_seconds)
        FotowareLog.info(
            f"New token expires at {FW_ACCESS_TOKEN_EXP.isoformat(timespec='minutes')}"
        )

    return FOTOWARE_ACCESS_TOKEN


async def GET(path, *, headers={}, **get_kwargs) -> dict:
    """GET request on the Fotoware ENDPOINT_HOST. Returns JSON."""
    FotowareLog.debug(f"GET {path} (with auth)")
    r = await SESSION.get(
        FOTOWARE_HOST + path,
        headers={"Accept": "application/json", **await auth_header(), **headers},
        allow_redirects=True,
        **get_kwargs,
    )
    return await r.json()


async def auth_header() -> dict[str, str]:
    """Return Authorization header as a dict"""
    return {"Authorization": f"Bearer {await access_token()}"}


async def PATCH(path, *, headers={}, data={}, **patch_kwargs) -> dict:
    """PATCH request on the Fotoware ENDPOINT_HOST"""
    FotowareLog.debug(f"PATCH {path} (with auth) {json.dumps(data)}")
    r = await SESSION.patch(
        FOTOWARE_HOST + path,
        headers={
            "Content-Type": "application/vnd.fotoware.assetupdate+json",
            "Accept": "application/vnd.fotoware.asset+json",
            **await auth_header(),
            **headers,
        },
        allow_redirects=True,
        json=data,
        **patch_kwargs,
    )

    if not r.ok:
        reason = await r.text()
        FotowareLog.error(f"Patch request '{path}' failed ({reason})")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=reason)

    return await r.json()


async def update_single_field(asset_href, field: str, value: str | list[str]):
    """Update a single metadata field with a new value of a single asset"""
    return await update_asset_metadata(asset_href, {field: {"value": value}})


async def update_asset_metadata(asset_href, metadata: dict) -> dict:
    """Update the metadata with the fields and values provided."""
    return await PATCH(asset_href, data={"metadata": metadata})


async def search_url(archive_id: str) -> str | None:
    """Get an archive's search URL. Some archives may not be searchable."""
    desc = await GET(f"/fotoweb/archives/{archive_id}/")
    return desc.get("searchURL")


async def rendition_request_service_url() -> str | None:
    api_descriptor = await GET("/fotoweb/me/")
    return api_descriptor.get("services", {}).get("rendition_request")
