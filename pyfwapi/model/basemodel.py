from pydantic import BaseModel, ConfigDict, field_validator


class APIResponse(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    @field_validator("*", mode="before")
    def empty_str_to_none(cls, value):
        if value == "":
            return None
        return value
