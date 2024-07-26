from dataclasses import dataclass

from httpx import HTTPStatusError

from pyfwapi.apiconnection import APIConnection
from pyfwapi.log import FotowareLog
from pyfwapi.model.asset import Asset, MetadataFieldType


@dataclass
class MetadataChange:
    asset_href: str
    field: str
    value: MetadataFieldType


class UploadManager:
    def __init__(self, connection: APIConnection) -> None:
        self.api = connection
        self.changes: set[MetadataChange] = set()

    def set_asset_metadata(self, asset: Asset, field: int, value: MetadataFieldType):
        """Update a single asset's metadata with a new value for a single field"""
        self.changes.add(
            MetadataChange(asset_href=asset.href, field=str(field), value=value)
        )

    def has_uncommited_changes(self) -> bool:
        return len(self.changes) >= 1

    async def commit(self):
        """Commit the changes to the FotoWare API."""

        for change in self.changes:
            try:
                await self.api.PATCH(
                    change.asset_href,
                    headers={
                        "Content-Type": "application/vnd.fotoware.assetupdate+json"
                    },
                    data={"metadata": {change.field: {"value": change.value}}},
                )
            except HTTPStatusError as err:
                FotowareLog.warning(f"{change} failed, because:", err)
                continue
            else:  # no exception occurred
                self.changes.remove(change)
