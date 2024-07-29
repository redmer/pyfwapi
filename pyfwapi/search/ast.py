import textwrap
import typing as t
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class SearchExpressionAST:
    """
    An Abstract Syntax Tree for FotoWare Search Expressions.

    Consider using SE (Seach Expression) for an easier, fluent-style API.

    Each AST node is either a terminal value with a single argument (VALUE, FIELD) or it
    its arguments are instances of the AST that it structures.
    """

    type: t.Literal["AND", "OR", "NOT", "FIELD_EQ", "FIELD", "VAL_RANGE", "VALUE"]
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

    def __repr__(self) -> str:
        arg1, arg2 = self.args
        if arg2 is None:
            return f"""( {self.type} {repr(arg1)} )"""
        return f"""( {self.type}
{textwrap.indent( repr(arg1), "    "*2)}
{textwrap.indent( repr(arg2), "    "*2)}
)"""


type DATE_TYPES = date | datetime
type VALUE_TYPES = str | int | DATE_TYPES
type FIELD_TYPES = str | int


# MARK: Terminals
def VALUE(value: VALUE_TYPES):
    if isinstance(value, str) and " " in value:
        value = f'"{value}"'
    if isinstance(value, datetime):
        value = value.isoformat(sep="T", timespec="minutes")
    if isinstance(value, date):
        value = value.isoformat()
    return SearchExpressionAST(type="VALUE", args=(str(value), None))


def FIELD(fieldname: FIELD_TYPES):
    return SearchExpressionAST(type="FIELD", args=(str(fieldname), None))


# MARK: Non-terminals
def VAL_RANGE(start_value: SearchExpressionAST, end_value: SearchExpressionAST):
    return SearchExpressionAST(type="VAL_RANGE", args=(start_value, end_value))


def FIELD_EMPTY(field: SearchExpressionAST):
    return SearchExpressionAST(type="FIELD_EQ", args=(field, VALUE("")))


def FIELD_EQ(field: SearchExpressionAST, value: SearchExpressionAST):
    if not isinstance(value, SearchExpressionAST) or field.type != "FIELD":
        raise NotImplementedError()
    return SearchExpressionAST(type="FIELD_EQ", args=(field, value))


def NOT(lhs: SearchExpressionAST):
    if not isinstance(lhs, SearchExpressionAST):
        raise NotImplementedError()
    return SearchExpressionAST(type="NOT", args=(lhs, None))


def OR(lhs: SearchExpressionAST, rhs: SearchExpressionAST):
    if not isinstance(rhs, SearchExpressionAST):
        raise NotImplementedError()
    return SearchExpressionAST(type="OR", args=(lhs, rhs))


def AND(lhs: SearchExpressionAST, rhs: SearchExpressionAST):
    if not isinstance(rhs, SearchExpressionAST):
        raise NotImplementedError()
    return SearchExpressionAST(type="AND", args=(lhs, rhs))
