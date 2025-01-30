class APIError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class CollectionNotSearchable(APIError):
    pass


class UploadException(APIError):
    pass


class CollectionNotMovableTo(APIError):
    pass


class SearchSyntaxError(ValueError):
    pass
