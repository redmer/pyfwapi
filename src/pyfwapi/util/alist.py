import typing as t


async def alist[T](iterable: t.AsyncIterable[T]) -> t.List[T]:
    return list([i async for i in iterable])
