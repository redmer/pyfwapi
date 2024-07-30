import typing as t

from pydantic import Field

from pyfwapi.model.basemodel import APIResponse


class FieldNamespace(APIResponse):
    url: str = Field(alias="Url")
    alias: str = Field(alias="Alias")
    name: str = Field(alias="Name")


class KnownMetadataField(APIResponse):
    id: int = Field(alias="Id")
    name: str = Field(alias="Name")
    gui_label: str = Field(alias="GuiLabel")
    field_type: t.Literal["AltLang", "Bag", "Seq", "Single"] = Field(alias="FieldType")
    value_type: t.Literal["Boolean", "Date", "Integer", "Real", "Text"] = Field(
        alias="ValueType"
    )
    namespace: str = Field(alias="Namespace")
    namespace_label: str = Field(alias="NamespaceLabel")
    max_size: int = Field(alias="MaxSize")
    struct_name: str = Field(alias="StructName")
    struct_label: str = Field(alias="StructLabel")
    adobe_name: str = Field(alias="AdobeName")
    core_name: str = Field(alias="CoreName")
    is_multiline: bool = Field(alias="IsMultiline")


class Services(APIResponse):
    search: str | None
    rendition_request: str | None


class FullAPIDescriptor(APIResponse):
    services: Services
    searchURL: str
