from pydantic import BaseModel, ConfigDict, field_validator


class APIResponse(BaseModel):
    model_config = ConfigDict(
        extra="allow"  # , ignored_types=(APIConnection,), arbitrary_types_allowed=True
    )

    # __pyfwapi_connection__: APIConnection

    # @property
    # def api(self) -> APIConnection:
    #     return self.__pyfwapi_connection__

    @field_validator("*", mode="before")
    def empty_str_to_none(cls, value):
        if value == "":
            return None
        return value
