import textwrap
import typing as t
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class SearchSyntaxError(ValueError):
    pass


class Predicate(StrEnum):
    FileModification = "mt"
    FileModificationFrom = "mtf"
    FileModificationTo = "mtt"

    FileSize = "fs"
    FileSizeFrom = "fsf"
    FileSizeTo = "fst"

    PixelHeight = "ph"
    PixelHeightFrom = "phf"
    PixelHeightTo = "pht"

    PixelWidth = "pw"
    PixelWidthFrom = "pwf"
    PixelWidthTo = "pwt"

    FileName = "fn"
    DirectoryName = "dn"
    FullFilePath = "fp"
    ColorSpace = "cs"
    ImageOrientation = "o"
    AssetType = "dt"


@dataclass
class SearchExpressionAST:
    """
    An Abstract Syntax Tree for FotoWare Search Expressions. You can probably better use
    SE (Seach Expression) for an easier, fluent-style API.
    """

    type: t.Literal[
        "AND", "OR", "NOT", "FIELD_EQ", "FIELD", "VAL_RANGE", "VALUE", "NOOP"
    ]
    args: tuple[t.Self | str, t.Self | str | None]

    def __str__(self) -> str:
        arg1, arg2 = self.args
        match self.type:
            case "VALUE" | "FIELD":
                return str(arg1)
            case "VAL_RANGE":
                return f"{str(arg1)}~~{str(arg2)}"
            case "FIELD_EQ":
                return f"{str(arg1)}:{str(arg2)}"
            case "NOT":
                return f"NOT ( {str(arg1)} )"
            case "OR" | "AND":
                return f"( {str(arg1)} ) {self.type} ( {str(arg2)} )"
            case _:
                return ""

    def __repr__(self) -> str:
        arg1, arg2 = self.args
        if arg2 is None:
            return f"""( {self.type} {repr(arg1)} )"""
        return f"""( {self.type}
{textwrap.indent( repr(arg1), "    "*2)}
{textwrap.indent( repr(arg2), "    "*2)}
)"""

    # MARK: Terminals
    @classmethod
    def VALUE(cls, value: str | int | date | datetime):
        if isinstance(value, str) and " " in value:
            value = f'"{value}"'
        if isinstance(value, datetime):
            value = value.isoformat(sep="T", timespec="minutes")
        if isinstance(value, date):
            value = value.isoformat()
        return cls(type="VALUE", args=(str(value), None))

    @classmethod
    def FIELD(cls, fieldname: str | int):
        return cls(type="FIELD", args=(str(fieldname), None))

    # MARK: Non-terminals
    @classmethod
    def VAL_RANGE(cls, start_value: t.Self, end_value: t.Self):
        return cls(type="VAL_RANGE", args=(start_value, end_value))

    @classmethod
    def FIELD_EMPTY(cls, field: t.Self):
        return cls(type="FIELD_EQ", args=(field, cls.VALUE("")))

    @classmethod
    def FIELD_EQ(cls, field: t.Self, value: t.Self):
        if not isinstance(value, cls) or field.type != "FIELD":
            raise NotImplementedError()
        return cls(type="FIELD_EQ", args=(field, value))

    @classmethod
    def NOT(cls, lhs: t.Self):
        if not isinstance(lhs, cls):
            raise NotImplementedError()
        return cls(type="NOT", args=(lhs, None))

    @classmethod
    def OR(cls, lhs: t.Self, rhs: t.Self):
        if not isinstance(rhs, cls):
            raise NotImplementedError()
        return cls(type="OR", args=(lhs, rhs))

    @classmethod
    def AND(cls, lhs: t.Self, rhs: t.Self):
        if not isinstance(rhs, cls):
            raise NotImplementedError()
        return cls(type="AND", args=(lhs, rhs))


# SearchExpression
class SE:
    """
    Search Expression. A fluent-style builder for Full Text Search, predicated search,
    search for ranges, combinable with `|` (OR), `&` (AND) and `-` (NOT).

    Every method returns itself, so you can combine multiple filters easily. By default,
    these are combined using AND.

    >>> SE()
            .range("dt", min=today() - timedelta(days=2, hours=4), max=today())
            | SE().eq("fn", "*.png")
            & SE().fts("example").fts("pride")

    Reference: <https://learn.fotoware.com/FotoWare_SaaS/Navigating_and_searching_to_find_your_assets/Searching_in_FotoWare/001_Searching_for_assets/FotoWare_Search_Expressions_Reference>
    """

    data: SearchExpressionAST | None

    def __init__(self) -> None:
        self.data = None
        pass

    def fts(self, value: str, /):
        """Full text search"""

        ast = SearchExpressionAST.VALUE(value)

        self.data = SearchExpressionAST.AND(self.data, ast) if self.data else ast
        return self

    def empty(self, field: str | int, /):
        """Search for empty values"""
        ast = SearchExpressionAST.FIELD_EMPTY(SearchExpressionAST.FIELD(field))

        self.data = SearchExpressionAST.AND(self.data, ast) if self.data else ast
        return self

    def eq(self, field: str | int, value: str | int | date | datetime, /):
        """Search for field that equals value"""

        ast = SearchExpressionAST.FIELD_EQ(
            SearchExpressionAST.FIELD(field), SearchExpressionAST.VALUE(value)
        )

        self.data = SearchExpressionAST.AND(self.data, ast) if self.data else ast
        return self

    def range(
        self,
        field: str | int,
        /,
        *,
        min: str | int | date | datetime,
        max: str | int | date | datetime,
    ):
        """Search for field values in range"""
        ast = SearchExpressionAST.FIELD_EQ(
            SearchExpressionAST.FIELD(field),
            SearchExpressionAST.VAL_RANGE(
                SearchExpressionAST.VALUE(min), SearchExpressionAST.VALUE(max)
            ),
        )

        self.data = SearchExpressionAST.AND(self.data, ast) if self.data else ast
        return self

    def NOT(self, other: t.Self | None = None, /):
        """
        This negates the passed Search Expression or negates the current built
        SearchExpression.
        """
        if self.data:
            if other and other.data:
                self.data = SearchExpressionAST.AND(
                    self.data, SearchExpressionAST.NOT(other.data)
                )
            else:  # zero argument, negates itself
                self.data = SearchExpressionAST.NOT(self.data)
        else:  # zero self.data, negates other
            if other and other.data:
                self.data = SearchExpressionAST.NOT(other.data)
            else:
                raise SearchSyntaxError("No initialized parts in a negated SE")

        return self

    def __neg__(self):
        return self.NOT()

    def OR(self, other: t.Self, /):
        if other.data is None or self.data is None:
            raise SearchSyntaxError("Uninitialized SE in an OR expression")
        self.data = SearchExpressionAST.OR(self.data, other.data)
        return self

    def __or__(self, other):
        if not isinstance(other, self.__class__):
            raise NotImplementedError()
        return self.OR(other)

    def AND(self, other: t.Self, /):
        if other.data is None or self.data is None:
            raise SearchSyntaxError("Uninitialized SE in an AND expression")
        self.data = SearchExpressionAST.AND(self.data, other.data)
        return self

    def __and__(self, other):
        if not isinstance(other, self.__class__):
            raise NotImplementedError()
        return self.AND(other)

    def __str__(self) -> str:
        return str(self.data)

    def __repr__(self) -> str:
        return f"""SE(ast={repr(self.data)})"""
