import requests

from ..config import FOTOWARE_EXPORT_PRESET_ID, FOTOWARE_HOST, HOST
from . import Asset, api
from .apitypes import ImageExport


def can_be_exported(asset: Asset):
    """This asset can be exported"""
    return asset["doctype"] in ["image"]


def export_locations(
    asset_href: str, *, width: int = 0, height: int = 0
) -> ImageExport:
    """Returns the permanent locations of exported assets"""
    response = requests.request(
        "EXPORT",
        FOTOWARE_HOST + asset_href,
        headers={
            "Content-Type": "application/vnd.fotoware.export-request+json",
            "Accept": "application/vnd.fotoware.export-data+json",
            **api.auth_header(),
        },
        json={
            "width": width,
            "height": height,
            "publication": HOST,
            "preset": f"/fotoweb/me/presets/export/{ FOTOWARE_EXPORT_PRESET_ID }",
        },
    )
    return response.json()["export"]["image"]
