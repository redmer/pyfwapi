import typing as t

from pyfwapi.apiconnection import APIConnection
from pyfwapi.errors import CollectionNotMovableTo
from pyfwapi.model.asset import Asset, MetadataFieldType
from pyfwapi.model.collection import Collection

from .stateful import (
    BaseChangeManager,
    ChangeTask,
    MetadataAttributesPatch,
    MetadataPatch,
    MetadataRequest,
    MoveRequest,
    UploadRequest,
    ValueMetadataField,
)


class ChangeManager:
    """
    Prepare and commit changes to assets. That includes changed metadata, to upload new
    files and moving files.
    """

    def __init__(self, connection: APIConnection) -> None:
        self.api = connection
        self.state = BaseChangeManager()

    async def commit(self):
        """Commit the changes to the backend API. This may take a while."""
        await self.state.commit(conn=self.api)

    # Metadata change
    def set_value(self, asset: Asset, field: int, value: MetadataFieldType, /):
        """Set metadata attribute for an Asset."""
        self.state.add_task(
            ChangeTask(change=MetadataRequest(asset.href, {field: {"value": value}}))
        )

    def set_values(self, asset: Asset, metadata: dict[int, ValueMetadataField], /):
        """Set metadata attributes for an Asset. Value passed on as-is."""
        self.state.add_task(ChangeTask(change=MetadataRequest(asset.href, metadata)))

    # Move files
    def move(self, assets: t.Iterable[Asset], /, destination: Collection):
        """
        Move assets to a different Collection.

        Raises:
            MoveTargetError: if the destination Collection is not a valid destination,
                e.g. because it is a search archive.
        """
        if not destination.canMoveTo:
            raise CollectionNotMovableTo(destination.name)

        hrefs = list(a.href for a in assets)
        self.state.add_task(ChangeTask(change=MoveRequest(hrefs, destination.href)))

    # upload new assets
    def upload(
        self,
        file: t.BinaryIO,
        destination: Collection,
        *,
        filename: str | None = None,
        fields: list[MetadataPatch] | None = None,
        attributes: list[MetadataAttributesPatch] | None = None,
    ):
        """
        Upload a new asset, from a local file of filestream.

        Args:
            file: An opened file-like stream.
            destination: the archive to upload to.
            filename: the file's name, taken from file.name if None.
            fields: arbitrairy custom metadata.
            attributes: change the file's modification datetime.

        Raises:
            MoveTargetError: if the destination Collection is not a valid destination,
                e.g. because it is a search archive.
        """
        if not destination.canUploadTo:
            raise CollectionNotMovableTo(destination.name)

        fn = filename or file.name
        contents = memoryview(file.read())
        contents.nbytes
        self.state.add_task(
            ChangeTask(
                change=UploadRequest(
                    contents,
                    destination.href,
                    fn,
                    contents.nbytes,
                    fields or [],
                    attributes or [],
                )
            )
        )


__all__ = ["ChangeManager"]
