from pyfwapi.model.basemodel import APIResponse


class Services(APIResponse):
    search: str | None
    rendition_request: str | None


class InstanceInfo(APIResponse):
    services: Services
    searchURL: str
