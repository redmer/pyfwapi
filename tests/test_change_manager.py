from io import BytesIO
from unittest.mock import MagicMock

import pytest

from pyfwapi.apiconnection import APIConnection
from pyfwapi.change.manager import ChangeManager
from pyfwapi.change.stateful import MetadataRequest, MoveRequest, UploadRequest
from pyfwapi.errors import CollectionNotMovableTo
from pyfwapi.model.asset import Asset
from pyfwapi.model.collection import Collection


class TestChangeManager:
    @pytest.fixture
    def mock_conn(self):
        return MagicMock(spec=APIConnection)

    @pytest.fixture
    def manager(self, mock_conn):
        return ChangeManager(mock_conn)

    @pytest.fixture
    def asset(self):
        return Asset.model_construct(
            href="/fotoweb/archives/1/asset1",
            metadata={},
            builtinFields=[],
            doctype="image",
            attributes={},
        )

    @pytest.fixture
    def collection(self):
        return Collection.model_construct(
            id="1",
            name="Archive 1",
            href="/fotoweb/archives/1",
            data="/fotoweb/archives/1/data",
            type="archive",
            searchURL="/search",
            originalURL="/original",
            isSearchable=True,
            permissions=[],
            canMoveTo=True,
            canUploadTo=True,
            description="",
        )

    def test_set_value(self, manager, asset):
        manager.set_value(asset, 10, "New Value")

        tasks = list(manager.state.tasks.values())
        assert len(tasks) == 1

        req = tasks[0].change
        assert isinstance(req, MetadataRequest)
        assert req.asset_href == "/fotoweb/archives/1/asset1"
        assert req.new_metadata == {10: {"value": "New Value"}}

    def test_set_values(self, manager, asset):
        manager.set_values(asset, {10: {"value": "Value 1"}, 20: {"value": "Value 2"}})

        tasks = list(manager.state.tasks.values())
        assert len(tasks) == 1

        req = tasks[0].change
        assert isinstance(req, MetadataRequest)
        assert req.new_metadata == {10: {"value": "Value 1"}, 20: {"value": "Value 2"}}

    def test_move_success(self, manager, asset, collection):
        manager.move([asset], collection)

        tasks = list(manager.state.tasks.values())
        assert len(tasks) == 1

        req = tasks[0].change
        assert isinstance(req, MoveRequest)
        assert req.asset_hrefs == ["/fotoweb/archives/1/asset1"]
        assert req.destination == collection.href

    def test_move_fails_cannot_move(self, manager, asset):
        collection = Collection.model_construct(
            id="1", name="Archive 1", href="/fotoweb/archives/1", canMoveTo=False
        )
        with pytest.raises(CollectionNotMovableTo):
            manager.move([asset], collection)

    def test_upload_success(self, manager, collection):
        file_obj = BytesIO(b"file contents")
        file_obj.name = "test.png"

        manager.upload(file_obj, collection)

        tasks = list(manager.state.tasks.values())
        assert len(tasks) == 1

        req = tasks[0].change
        assert isinstance(req, UploadRequest)
        assert req.filename == "test.png"
        assert req.destination == collection.href
        assert req.filesize == len(b"file contents")

    def test_upload_fails_cannot_upload(self, manager):
        collection = Collection.model_construct(
            id="1", name="Archive 1", href="/fotoweb/archives/1", canUploadTo=False
        )
        file_obj = BytesIO(b"file contents")
        file_obj.name = "test.png"

        with pytest.raises(CollectionNotMovableTo):
            manager.upload(file_obj, collection)
