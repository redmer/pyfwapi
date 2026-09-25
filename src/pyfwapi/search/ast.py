"""
This module provides a dataclass that can represent an Abstract Syntax Tree for FotoWare
Search Expressions.

Consider using SE (Seach Expression) for an easier, fluent-style API.
"""

import json
import textwrap
import typing as t
from dataclasses import dataclass
from datetime import date, datetime, timezone


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
{textwrap.indent(repr(arg1), "    " * 2)}
{textwrap.indent(repr(arg2), "    " * 2)}
)"""


type DATE_TYPES = date | datetime
type VALUE_TYPES = str | int | DATE_TYPES
type FIELD_TYPES = str | int

# Reserved words and delimiter characters that force a term to be quoted as a phrase.
# Note: ':' is intentionally not reserved; it appears in date/time terms such as
# '2023-05-17T12:25:00Z', which must stay unquoted in range/field contexts.
_RESERVED_WORDS = {"and", "or", "not", "to"}
_RESERVED_CHARS = set('"&|()~\\')


def _quote_phrase(value: str) -> str:
    """Quote a string as a phrase, using JSON string syntax (escape sequences)."""
    return json.dumps(value, ensure_ascii=False)


def _needs_quoting(value: str) -> bool:
    """Check if a term must be quoted to keep its literal meaning."""
    if not value:
        return False
    if value.lower() in _RESERVED_WORDS:
        return True
    # A leading hyphen is the NOT operator; mid-word hyphens are literal.
    if value.startswith("-"):
        return True
    return any(c.isspace() or c in _RESERVED_CHARS for c in value)


# MARK: Terminals
def VALUE(value: VALUE_TYPES):
    """Create a field value, escaped where necessary"""
    if isinstance(value, str) and _needs_quoting(value):
        value = _quote_phrase(value)
    if isinstance(value, datetime):
        # FotoWeb expects ISO 8601 with seconds and prefers UTC ('Z').
        # Naive datetimes are assumed to be UTC.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = (
            value.astimezone(timezone.utc)
            .isoformat(sep="T", timespec="seconds")
            .replace("+00:00", "Z")
        )
    elif isinstance(value, date):
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
