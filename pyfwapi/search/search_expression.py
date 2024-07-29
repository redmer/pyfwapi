import typing as t

from pyfwapi.model.asset import (
    AssetTypeValues,
    ColorSpaceValues,
    ImageOrientationValues,
)
from pyfwapi.search.ast import (
    AND,
    DATE_TYPES,
    FIELD,
    FIELD_EMPTY,
    FIELD_EQ,
    FIELD_TYPES,
    NOT,
    OR,
    VAL_RANGE,
    VALUE,
    VALUE_TYPES,
    SearchExpressionAST,
)
from pyfwapi.search.errors import SearchSyntaxError
from pyfwapi.search.predicates import Ranged, StrSpecial


class SE:
    """
    Search Expression. A fluent-style builder for Full Text Search, predicated search,
    search for ranges and infinitely combinable with boolean operators.

    Every method returns a copy of itself, so you can combine multiple filters easily.
    These are generally combined using AND. Use `|` `OR()` and `-` `NOT()` to combine
    terms in other ways (for explicitely query building, you may also use `&` `AND()`).

    >>> SE()
            .range("dt", min=today() - timedelta(days=2, hours=4), max=today())
            | SE().eq("fn", "*.png")
            & SE().fts("example").fts("pride")

    Note that for `empty()`, the index manager MUST index empty values for that field.
    Otherwise, results may be incomplete.

    Some fields have specialized matching functions, like `assettype`, `colorspace`,
    `image_orientation`, `modification`, `filesize`, `pixel_height`, `pixel_width`.

    Reference: <https://learn.fotoware.com/FotoWare_SaaS/Navigating_and_searching_to_find_your_assets/Searching_in_FotoWare/001_Searching_for_assets/FotoWare_Search_Expressions_Reference>
    """

    data: SearchExpressionAST | None

    def __init__(self, ast: SearchExpressionAST | None = None) -> None:
        self.data = ast

    def fts(self, value: str, /):
        """Search across all metadata (full text search)"""

        ast = VALUE(value)
        return SE(AND(self.data, ast) if self.data else ast)

    def empty(self, field: str | int, /):
        """Search for empty values"""
        ast = FIELD_EMPTY(FIELD(field))
        return SE(AND(self.data, ast) if self.data else ast)

    @t.overload
    def eq(self, field: StrSpecial, value: str, /): ...
    @t.overload
    def eq(self, field: FIELD_TYPES, value: VALUE_TYPES, /): ...
    def eq(self, field: FIELD_TYPES | StrSpecial, value: VALUE_TYPES, /):
        """Search for an exact field value"""

        ast = FIELD_EQ(FIELD(field), VALUE(value))
        return SE(AND(self.data, ast) if self.data else ast)

    def colorspace(self, value: ColorSpaceValues, /) -> t.Self:
        return self.eq(StrSpecial.ColorSpace, value)

    def image_orientation(self, value: ImageOrientationValues, /) -> t.Self:
        return self.eq(StrSpecial.ImageOrientation, value)

    def assettype(self, value: AssetTypeValues, /) -> t.Self:
        return self.eq(StrSpecial.AssetType, value)

    def range(self, field: FIELD_TYPES | Ranged, min: VALUE_TYPES, max: VALUE_TYPES, /):
        """Search for field values in range"""
        ast = FIELD_EQ(FIELD(field), VAL_RANGE(VALUE(min), VALUE(max)))
        return SE(AND(self.data, ast) if self.data else ast)

    def _minmax(
        self, field: Ranged, min: VALUE_TYPES | None, max: VALUE_TYPES | None, /
    ):
        if min is not None and max is not None:
            return self.range(field, min, max)
        if min is not None:
            return self.eq(str(field) + "f", min)
        if max is not None:
            return self.eq(str(field) + "t", max)
        raise SearchSyntaxError("A ranged value must have either a min, a max or both.")

    def modification(self, min: DATE_TYPES | None, max: DATE_TYPES | None, /):
        return self._minmax(Ranged.FileModification, min, max)

    def filesize(self, min: int | None, max: int | None, /):
        return self._minmax(Ranged.FileSize, min, max)

    def pixel_height(self, min: int | None, max: int | None, /):
        return self._minmax(Ranged.PixelHeight, min, max)

    def pixel_width(self, min: int | None, max: int | None, /):
        return self._minmax(Ranged.PixelWidth, min, max)

    def NOT(self, other: t.Self | None = None, /):
        """
        This negates the passed Search Expression or negates the current built
        SearchExpression.
        """
        if self.data:
            if other and other.data:
                return SE(AND(self.data, NOT(other.data)))

            return SE(NOT(self.data))  # zero argument, negates itself

        if other and other.data:
            return SE(NOT(other.data))

        raise SearchSyntaxError("Uninitialized SE in a NOT expression")

    def __neg__(self):
        return self.NOT()

    def OR(self, other: t.Self, /):
        if other.data is None or self.data is None:
            raise SearchSyntaxError("Uninitialized SE in an OR expression")
        return SE(OR(self.data, other.data))

    def __or__(self, other):
        if not isinstance(other, self.__class__):
            raise NotImplementedError()
        return self.OR(other)

    def AND(self, other: t.Self, /):
        if other.data is None or self.data is None:
            raise SearchSyntaxError("Uninitialized SE in an AND expression")
        return SE(AND(self.data, other.data))

    def __and__(self, other):
        if not isinstance(other, self.__class__):
            raise NotImplementedError()
        return self.AND(other)

    def __str__(self) -> str:
        return str(self.data)

    def __repr__(self) -> str:
        return f"""SE(ast={repr(self.data)})"""


__all__ = ["SE"]
