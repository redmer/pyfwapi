import json
from datetime import datetime, timedelta
from typing import Tuple

import requests
from fastapi import HTTPException

from .. import persistence
from ..config import FOTOWARE_CLIENT_ID, FOTOWARE_CLIENT_SECRET, FOTOWARE_HOST
from .apitypes import *
from .log import FotowareLog


def access_token() -> str:
    """Get the OAuth2 Access Token from the environment variables CLIENT_ID and CLIENT_SECRET"""

    def request_new_access_token() -> Tuple[str, float]:
        FotowareLog.debug(f"Requesting NEW access token")
        r = requests.post(
            FOTOWARE_HOST + "/fotoweb/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": FOTOWARE_CLIENT_ID,
                "client_secret": FOTOWARE_CLIENT_SECRET,
            },
            allow_redirects=True,
            headers={"Accept": "application/json"},
        )
        response = r.json()
        return response["access_token"], response["expires_in"]

    value = persistence.get("fotoware_access_token")

    if value is not None:
        return str(value, encoding="utf-8")

    if value is None:
        value, exp_in_seconds = request_new_access_token()
        expiration = (datetime.now() + timedelta(seconds=exp_in_seconds)).isoformat(
            timespec="minutes"
        )
        FotowareLog.info(f"New token expires at {expiration}")
        persistence.set(
            "fotoware_access_token",
            value,
            expires_in=int(exp_in_seconds),
        )
        return value
    return value


def GET(path, *, headers={}, **get_kwargs) -> dict:
    """GET request on the Fotoware ENDPOINT_HOST. Returns JSON."""
    FotowareLog.debug(f"GET {path} (with auth)")
    r = requests.get(
        f"{FOTOWARE_HOST}{path}",
        headers={"Accept": "application/json", **auth_header(), **headers},
        allow_redirects=True,
        **get_kwargs,
    )
    return r.json()


def auth_header() -> dict[str, str]:
    """Return Authorization header as a dict"""
    return {"Authorization": f"Bearer {access_token()}"}


def PATCH(path, *, headers={}, data={}, **patch_kwargs) -> dict:
    """PATCH request on the Fotoware ENDPOINT_HOST"""
    FotowareLog.debug(f"PATCH {path} (with auth) {json.dumps(data)}")
    r = requests.patch(
        f"{FOTOWARE_HOST}{path}",
        headers={
            "Content-Type": "application/vnd.fotoware.assetupdate+json",
            "Accept": "application/vnd.fotoware.asset+json",
            **auth_header(),
            **headers,
        },
        allow_redirects=True,
        data=json.dumps(data),
        **patch_kwargs,
    )

    if not r.ok:
        raise HTTPException(r.status_code, r.reason)

    return r.json()


def update_single_field(asset_href, field: str, value: str | list[str]):
    """Update a single metadata field with a new value of a single asset"""
    return update_asset_metadata(asset_href, {field: {"value": value}})


def update_asset_metadata(asset_href, metadata: dict) -> dict:
    """Update the metadata with the fields and values provided."""
    return PATCH(asset_href, data={"metadata": metadata})


def search_url(archive_id: str) -> str | None:
    """Get an archive's search URL. Some archives may not be searchable."""
    desc = GET(f"/fotoweb/archives/{archive_id}/")
    return desc.get("searchURL")


def rendition_request_service_url() -> str | None:
    api_descriptor = GET("/fotoweb/me/")
    return api_descriptor.get("services", {}).get("rendition_request")
