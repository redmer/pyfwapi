from fastapi import HTTPException, status

from . import api
from .api import AssetRendition
from .apitypes import Asset
from .log import FotowareLog


def has_renditions(asset: Asset):
    """This asset can be rendered"""
    return isinstance(asset.get("renditions"), list)


def original_rendition(renditions: list[AssetRendition]) -> AssetRendition:
    """Return the original rendition of the asset"""
    qualified = filter(lambda r: True == r["original"], renditions)
    return next(qualified)


def find_rendition(
    data: list[AssetRendition],
    *,
    profile: str | None = None,
    size: int = 0,
    width: int = 0,
    height: int = 0,
    original: bool | None = None,
) -> AssetRendition | None:
    """Find the first rendition URL that qualifies with the specified constraints"""
    qualified = data

    if profile is not None:
        qualified = filter(lambda i: profile == i["profile"], qualified)
    if original is not None:
        qualified = filter(lambda i: original == i["original"], qualified)

    # A SIZE equals the length of the longest side. Matching a minimum size, the shortest
    # (= min()) side should determine match.
    qualified = filter(lambda i: size <= min([i["height"], i["width"]]), qualified)
    qualified = filter(lambda i: width <= i["width"], qualified)
    qualified = filter(lambda i: height <= i["height"], qualified)
    return next(qualified)  # next = first = qualified[0]


async def rendition_location(rendition: AssetRendition) -> str:
    service = await api.rendition_request_service_url()
    if service is None:
        FotowareLog.error(f"There is no Fotoware endpoint for Rendition Requests.")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)

    rendition_href = rendition["href"]
    try:
        start_render = await api.SESSION.post(
            api.FOTOWARE_HOST + service,
            headers={
                "Content-Type": "application/vnd.fotoware.rendition-request+json",
                "Accept": "application/vnd.fotoware.rendition-response+json",
                **await api.auth_header(),
            },
            json={"href": rendition_href},
        )
        print(f"{start_render=}")
        start_render.raise_for_status()
        return start_render.headers["Location"]
    except BaseException as e:
        FotowareLog.error(f"Rendition request '{rendition_href}' failed ({e=})")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)
