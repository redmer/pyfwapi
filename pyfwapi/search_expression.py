from collections import UserString
from enum import StrEnum


class Predicate(StrEnum):
    FileModificationFrom = "mtf"
    FileName = "fn"
    # ... other predicates not implemented yet


class SE(UserString):
    """
    Search expression builder.  It represents a Full Text Search, a predicated search
    and can combine SE's with | (OR), & (AND) and - (NOT).

    Reference: <https://learn.fotoware.com/FotoWare_SaaS/Navigating_and_searching_to_find_your_assets/Searching_in_FotoWare/001_Searching_for_assets/FotoWare_Search_Expressions_Reference>
    """

    @classmethod
    def escape(cls, value: str, /):
        """Escape certain chars in the search expression query"""
        return value.translate(
            str.maketrans(
                {
                    "\b": R"\b",
                    "\f": R"\f",
                    "\n": R"\n",
                    "\r": R"\r",
                    "\t": R"\t",
                    '"': R"\"",
                    "\\": R"\\",
                },
            )
        )

    @classmethod
    def fts(cls, value: str, /):
        """Full text search"""
        return SE(SE.escape(value))

    @classmethod
    def empty(cls, field: str, /):
        """Search for empty values"""
        return SE(f'{field}:""')

    @classmethod
    def eq(cls, field: str, value: str, /):
        """Search for field that equals value"""
        return SE(f'{field}:"{ SE.escape(value) }"')

    @classmethod
    def range(cls, field: str, /, *, min: int | str, max: int | str):
        """Search for field values in range"""
        return SE(f"{field}:{min}~~{max}")

    def __neg__(self):
        """Negate a search expression"""
        return SE(f"NOT ( {self} )")

    def __or__(self, other):
        """Combine a search expression with OR"""
        if other is None:
            return self
        if not isinstance(other, SE):
            raise NotImplementedError()
        return SE(f"( {self} ) OR ( {other} )")

    def __and__(self, other):
        """Combine a search expression with AND"""
        if other is None:
            return self
        if not isinstance(other, SE):
            raise NotImplementedError()
        return SE(f"( {self} ) AND ( {other} )")

    def __str__(self) -> str:
        return self.data
