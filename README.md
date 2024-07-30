# `pyfwapi`

Work with the Fotoware API in Python.

## Examples

```py
>>> from pyfwapi import Tenant
... fw = Tenant("https://tenant.example.org", client_id="abd123", client_secret="sekret")
...
... async for archive in fw.archives():
...     print(a.name)
Marketing
Technical docs
```

## Design considerations

The API responses are parsed using Pydantic.
It's a hefty dependency, but -- for now -- allows easy parsing of the JSON responses.
And it also enables easy integration with FastAPI.

Explorations of `attrs`, `cattrs`, and `msgspec` failed to quickly result in satisfactory objects from the API JSON responses.
