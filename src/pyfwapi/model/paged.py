from pyfwapi.model.basemodel import APIResponse


class PagingInfo(APIResponse):
    """URLs to other pages in this paged resource."""

    prev: str
    next: str
    first: str
    last: str


class Paged[T](APIResponse):
    data: list[T]
    paging: PagingInfo | None
