"""
This module provides a dataclass that can represent an Abstract Syntax Tree for FotoWare
Search Expressions.

Consider using SE (Seach Expression) for an easier, fluent-style API.
"""

import textwrap
import typing as t
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class SEASTNode:
    """
    An Abstract Syntax Tree node for FotoWare Search Expressions.

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
    """Create a field value, escaped where necessary"""
    if isinstance(value, str) and " " in value:
        value = f'"{value}"'
    if isinstance(value, datetime):
        value = value.isoformat(sep="T", timespec="minutes")
    if isinstance(value, date):
        value = value.isoformat()
    return SEASTNode(type="VALUE", args=(str(value), None))


def FIELD(fieldname: FIELD_TYPES):
    """Create a field"""
    return SEASTNode(type="FIELD", args=(str(fieldname), None))


# MARK: Non-terminals
def VAL_RANGE(start_value: SEASTNode, end_value: SEASTNode):
    """Create a ranged field value"""
    return SEASTNode(type="VAL_RANGE", args=(start_value, end_value))


def FIELD_EMPTY(field: SEASTNode):
    """Create an empty field expression"""
    return SEASTNode(type="FIELD_EQ", args=(field, VALUE("")))


def FIELD_EQ(field: SEASTNode, value: SEASTNode):
    """Create an field value expression"""
    if not isinstance(value, SEASTNode) or field.type != "FIELD":
        raise NotImplementedError()
    return SEASTNode(type="FIELD_EQ", args=(field, value))


def NOT(lhs: SEASTNode):
    """Negate a search expression"""
    if not isinstance(lhs, SEASTNode):
        raise NotImplementedError()
    return SEASTNode(type="NOT", args=(lhs, None))


def OR(lhs: SEASTNode, rhs: SEASTNode):
    """Combine two search expressions with OR"""
    if not isinstance(rhs, SEASTNode):
        raise NotImplementedError()
    return SEASTNode(type="OR", args=(lhs, rhs))


def AND(lhs: SEASTNode, rhs: SEASTNode):
    """Combine two search expressions with AND"""
    if not isinstance(rhs, SEASTNode):
        raise NotImplementedError()
    return SEASTNode(type="AND", args=(lhs, rhs))
