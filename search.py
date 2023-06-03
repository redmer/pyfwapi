from collections.abc import AsyncGenerator
from typing import Any, Iterable
from urllib.parse import quote

from fastapi import HTTPException, status

from .api import GET, search_url
from .apitypes import Asset
from .log import FotowareLog as logging
from .search_expression import SE

FOTOWARE_QUERY_PLACEHOLDER = "{?q}"


async def iter_paginated_assets(page_query: str) -> AsyncGenerator[Asset, None]:
    """Collect all assets from the pages in a collection."""

    page_url: str | None = page_query

    while page_url is not None:
        full_results = await GET(page_url)

        # The key "assets" is present only on the first page of results / when
        # representing a collection.
        page: dict[str, Any] = full_results.get("assets", full_results)
        data = page.get("data")  # type: list[Asset] | None

        if data is None:
            break

        logging.debug(f"Found {len(data)} assets")
        for a in data:
            yield a

        page_url = None
        try:
            page_url = page.get("paging", {}).get("next")  # type: str | None
        except AttributeError:
            pass  # breaks if page_url is None


async def iter_archives(
    archives: Iterable[str], query: SE
) -> AsyncGenerator[Asset, None]:
    """Find all (paginated) assets that match the query across archives"""

    for a in archives:
        search_base_url = await search_url(a)
        if search_base_url is None:
            logging.error(f"Archive '{a}' cannot be searched")
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

        q = ";o=+?q=" + quote(str(query).strip())  # order by oldest modified
        query_url = search_base_url.replace(FOTOWARE_QUERY_PLACEHOLDER, q)
        async for asset in iter_paginated_assets(query_url):
            yield asset


async def iter_n(
    archives: Iterable[str], query: SE, n: int = 25
) -> AsyncGenerator[Asset, None]:
    """Find /n/ results for query across supplied archives"""

    assets_iter = iter_archives(archives, query)
    for _ in range(n):
        try:
            asset = await anext(assets_iter)
            yield asset
        except StopAsyncIteration:
            pass


async def find_all(archives: Iterable[str], query: SE, n: int = 25) -> list[Asset]:
    """Find /n/ results for query across supplied archives"""

    results = []
    async for asset in iter_n(archives, query, n):
        results.append(asset)
    return results


async def find(archives: Iterable[str], query: SE) -> Asset:
    """Find a single asset that matches query in all supplied archives"""

    assets = await find_all(archives, query, n=2)

    if len(assets) == 0:
        logging.error(f"No assets match '{query}' (in archives {archives})")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if len(assets) > 1:
        logging.error(f"Multiple assets match '{query}' (in archives {archives})")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return assets[0]
