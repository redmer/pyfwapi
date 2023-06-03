from ..config import FOTOWARE_EXPORT_PRESET_ID, HOST
from . import api
from .apitypes import Asset, ImageExport


def can_be_exported(asset: Asset):
    """This asset can be exported"""
    return asset["doctype"] in ["image"]


async def export_locations(
    asset_href: str, *, width: int = 0, height: int = 0
) -> ImageExport:
    """Returns the permanent locations of exported assets"""
    r = await api.SESSION.request(
        "EXPORT",
        asset_href,
        headers={
            "Content-Type": "application/vnd.fotoware.export-request+json",
            "Accept": "application/vnd.fotoware.export-data+json",
            **await api.auth_header(),
        },
        json={
            "width": width,
            "height": height,
            "publication": HOST,
            "preset": f"/fotoweb/me/presets/export/{ FOTOWARE_EXPORT_PRESET_ID }",
        },
    )
    data = await r.json()
    return data["export"]["image"]
