class APIError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class ArchiveNotSearchableError(APIError):
    pass
