import itertools
from collections.abc import Generator
from typing import Iterable
from urllib.parse import quote

from fastapi import HTTPException, status

from .api import GET, search_url
from .apitypes import Asset
from .log import FotowareLog as logging
from .search_expression import SE

FOTOWARE_QUERY_PLACEHOLDER = "{?q}"


def iter_paginated_assets(page_query: str) -> Generator[Asset, None, None]:
    """Collect all assets from the pages in a collection."""

    full_results = GET(page_query)

    # The key "assets" is present only on the first page of results / when
    # representing a collection.
    page = full_results.get("assets", full_results)
    data = page.get("data")

    if data:
        logging.debug(f"Found {len(data)} assets")
        yield from data
    try:
        next_url = page.get("paging", {}).get("next")
        if next_url:
            yield from iter_paginated_assets(next_url)
    except AttributeError:
        pass


def iter_archives(archives: Iterable[str], query: SE) -> Generator[Asset, None, None]:
    """Find all (paginated) assets that match the query across archives"""

    for a in archives:
        search_base_url = search_url(a)
        if search_base_url is None:
            logging.error(f"Archive '{a}' cannot be searched")
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

        q = ";o=+?q=" + quote(str(query).strip())  # order by oldest modified
        search_query = search_base_url.replace(FOTOWARE_QUERY_PLACEHOLDER, q)
        yield from iter_paginated_assets(search_query)


def iter_n(archives: Iterable[str], query: SE, n: int = 25) -> Iterable[Asset]:
    """Find /n/ results for query across supplied archives"""

    return itertools.islice(iter_archives(archives, query), n)


def find_all(archives: Iterable[str], query: SE, n: int = 25) -> list[Asset]:
    """Find /n/ results for query across supplied archives"""

    return list(iter_n(archives, query, n))


def find(archives: Iterable[str], query: SE) -> Asset:
    """Find a single asset that matches query in all supplied archives"""

    assets = find_all(archives, query, n=2)

    if len(assets) == 0:
        logging.error(f"No assets match '{query}' (in archives {archives})")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if len(assets) > 1:
        logging.error(f"Multiple assets match '{query}' (in archives {archives})")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return assets[0]
