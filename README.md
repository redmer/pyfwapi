# `pyfwapi`

Work with the Fotoware API in Python.

## Examples

### Connect and iterate archives

Each server-side API endpoint is interacted with using a `Tenant`.
Create an non-interactive application integration server-side and supply the client ID and secret to the `Tenant`.

```py
>>> from pyfwapi import Tenant
>>> fw = Tenant("https://tenant.example.org", client_id="abd123", client_secret="sekret")
>>> async for archive in fw.iter_archives():
...     print(archive.name)
Marketing
Technical docs
```

### Iterate assets in an archive

Assets (files) are organized into archives.

```py
>>> archive = await fw.archive_by(id=5000)
>>> async for asset in fw.iter_assets(in_archive=archive):
...     print(asset.filename, asset.filesize)
 IMG_0021.jpg 27182818
 logo_v3_final_FINAL.pdf 3141592
```

### Search assets

`SE` builds search expressions fluently; combine terms with `&` (and), `|` (or), `-` (not).
Some properties that can be filtered on use abbreviated names, for which `predicates.StrSpecial` and `predicates.Ranged` are helpful.

```py
>>> from pyfwapi.search import SE, predicates
... # PNGs at least 500px tall, mentioning "banner"
>>> q = SE().fts("banner").eq(predicates.StrSpecial.FileName, "*.png").pixel_height(min=500, max=None)
>>> async for asset in fw.match_assets(q):
...     print(asset.filename)
```

### Previews and renditions

Previews are prerendered JPEGs, ready to download.
Renditions are async, configurable, and include the original file.

```py
>>> async for chunk in await fw.get_preview(asset, asset.previews[0]):
...     outfile.write(chunk)

>>> rendition = asset.renditions[0]
>>> async for chunk in await fw.get_rendition(rendition, "/renditions/image"):
...     outfile.write(chunk)
```

### Change metadata, move, and upload

Changes are staged in a `ChangeManager` and sent to the server in one go.
Note that these commits are neither atomic nor isolated, so parallel requests may find unmoved files during a commit.

```py
>>> from pyfwapi.change.manager import ChangeManager
>>> cm = ChangeManager(fw.api)
>>> cm.set_value(asset, 305, "Approved")          # set field 305
>>> cm.move([asset], destination=other_archive)   # move between archives
>>> with open("photo.jpg", "rb") as f:
...     cm.upload(f, archive, filename="photo.jpg")
>>> await cm.commit()
```

## Design considerations

The API responses are parsed using Pydantic.
It's a hefty dependency, but -- for now -- allows easy parsing of the JSON responses.
And it also enables easy integration with FastAPI.

Explorations of `attrs`, `cattrs`, and `msgspec` failed to quickly result in satisfactory objects from the API JSON responses.

The name of the library is a portmanteau of **Py**thon **F**oto**w**are **API** and I pronounce it as /paɪˈfwɒ.pi/.
