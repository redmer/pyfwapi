import typing as t
from urllib.parse import quote

from pyfwapi.apiconnection import APIConnection
from pyfwapi.errors import ArchiveNotSearchableError
from pyfwapi.log import FotowareLog
from pyfwapi.model.archive import Archive
from pyfwapi.model.asset import Asset
from pyfwapi.model.me import InstanceInfo
from pyfwapi.model.preview_rendition import AssetPreview, AssetRendition
from pyfwapi.search_expression import SE
from pyfwapi.util.alist import alist

from .apitypes import Asset
from .search_expression import SE

FOTOWARE_QUERY_PLACEHOLDER = "{?q}"


class Tenant:
    """The main interface to the FotoWare API for a specific tenant (instance)"""

    @t.overload
    def __init__(self, *, connection: APIConnection) -> None: ...
    @t.overload
    def __init__(self, url: str, *, client_id: str, client_secret: str) -> None: ...
    def __init__(
        self,
        url: str | None = None,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        connection: APIConnection | None = None,
    ) -> None:
        """
        Connect to an tenant (instance) of FotoWare. This is the core class to iterate
        archives and assets and to search for specific assets.

        Pass in either a connection or the three other arguments.

        Args:
            url: URL of the endpoint, e.g. `https://myorg.fotoware.cloud`
            client_id: the registered non-interactive application's `client_id`
            client_secret: the application's secret
            connection: reuse an existing API connection
        """

        if connection is None:
            if url is None or client_id is None or client_secret is None:
                raise TypeError()
            self.api = APIConnection(
                url, client_id=client_id, client_secret=client_secret
            )
        else:
            self.api = connection

    async def instance_info(self) -> InstanceInfo:
        d = await self.api.GET("/fotoweb/me")
        return InstanceInfo.model_validate_json(d.content)

    # MARK: Archives
    async def iter_archives(self) -> t.AsyncGenerator[Archive, None]:
        """Iterate over the (paginated) archives in this tenant."""
        async for archive in self.api.paginated("/fotoweb/archives", type=Archive):
            yield archive

    async def archive_by(self, *, id: int) -> Archive:
        """Get the archive with archive ID."""
        d = await self.api.GET(f"/fotoweb/archives/{id}")
        return Archive.model_validate_json(d.content)

    # MARK: Assets
    async def iter_assets(
        self, *, in_archive: Archive
    ) -> t.AsyncGenerator[Asset, None]:
        """Iterate over the (paginated) assets in this archive."""
        async for asset in self.api.paginated(in_archive.data, type=Asset):
            yield asset

    async def asset_by(self, *, href: str) -> Asset:
        """Get the asset with its href ID."""
        d = await self.api.GET(href)
        return Asset.model_validate_json(d.content)

    async def match_assets(
        self, *, query: SE, in_archives: list[Archive] | None = None
    ) -> t.AsyncGenerator[Asset, None]:
        archives = in_archives or await alist(self.iter_archives())

        for a in archives:
            search_base_url = a.searchURL
            if search_base_url is None:
                FotowareLog.error(f"Archive '{a}' cannot be searched")
                raise ArchiveNotSearchableError("Archive '{a}' has no searchURL")

            q = ";o=+?q=" + quote(str(query).strip())  # order by oldest modified
            query_url = search_base_url.replace(FOTOWARE_QUERY_PLACEHOLDER, q)
            async for asset in self.api.paginated(query_url, type=Asset):
                yield asset

    # MARK: Previews, renditions
    async def get_preview(
        self, asset: Asset, preview: AssetPreview
    ) -> t.AsyncIterator[bytes]:
        """Returns the bytes stream of the preview image"""

        r = await self.api.client.request(
            "GET",
            self.api.HOST + preview.href,
            withhold_token=True,
            headers={"Authorization": f"Bearer {asset.previewToken}"},
        )

        r.raise_for_status()
        return r.aiter_bytes()

    async def get_rendition(
        self, rendition: AssetRendition, endpoint: str
    ) -> t.AsyncIterator[bytes]:
        """
        Initiate a rendition request at the rendition request endpoint
        and wait until the bytestream is available
        """
        location = await self.request_rendition(rendition, endpoint)
        r = await self.api.retrying(location)
        return r.aiter_bytes()

    async def request_rendition(self, rendition: AssetRendition, endpoint: str) -> str:
        """
        Start a rendition request at the rendition request endpoint
        and return the URL (Location) where the rendition can be downloaded.

        Use get_rendition() for the rendition bytes stream and this method only if you
        need to intervene between rendention request and rendition ready.
        """

        r = await self.api.POST(
            self.api.HOST + endpoint,
            headers={
                "Content-Type": "application/vnd.fotoware.rendition-request+json",
                "Accept": "application/vnd.fotoware.rendition-response+json",
            },
            data={"href": rendition.href},
        )

        return r.headers["Location"]
