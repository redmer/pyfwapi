from datetime import date, datetime, timedelta, timezone

import pytest

from pyfwapi.search.ast import (
    FIELD,
    FIELD_EMPTY,
    FIELD_EQ,
    NOT,
    OR,
    VAL_RANGE,
    VALUE,
)


def test_ast_value():
    node = VALUE("test")
    assert node.type == "VALUE"
    assert str(node) == "test"


def test_ast_value_with_space():
    node = VALUE("hello world")
    assert str(node) == '"hello world"'


def test_ast_value_escapes_quotes_and_backslashes():
    node = VALUE('she said "hi"')
    assert str(node) == '"she said \\"hi\\""'

    node = VALUE("C:\\new")
    assert str(node) == '"C:\\\\new"'


def test_ast_value_quotes_reserved_words_and_delimiters():
    for word in ("AND", "or", "Not", "TO"):
        assert str(VALUE(word)) == f'"{word}"'
    for term in ("a&b", "a|b", "-prefix", "a(b)", "a~~b"):
        assert str(VALUE(term)) == f'"{term}"'


def test_ast_value_simple_terms_unquoted():
    assert str(VALUE("hello")) == "hello"
    assert str(VALUE("0123")) == "0123"
    assert str(VALUE("John-Fredrik")) == "John-Fredrik"
    assert str(VALUE("")) == ""


def test_ast_value_date():
    d = date(2026, 5, 7)
    node = VALUE(d)
    assert str(node) == "2026-05-07"


def test_ast_value_datetime():
    dt = datetime(2026, 5, 7, 14, 30)
    node = VALUE(dt)
    assert str(node) == "2026-05-07T14:30:00Z"


def test_ast_value_datetime_aware_converts_to_utc():
    dt = datetime(2026, 5, 7, 14, 30, tzinfo=timezone(timedelta(hours=2)))
    node = VALUE(dt)
    assert str(node) == "2026-05-07T12:30:00Z"


def test_ast_field():
    node = FIELD(100)
    assert node.type == "FIELD"
    assert str(node) == "100"


def test_ast_val_range():
    start = VALUE(10)
    end = VALUE(20)
    node = VAL_RANGE(start, end)
    assert node.type == "VAL_RANGE"
    assert str(node) == "10~~20"


def test_ast_field_eq():
    field = FIELD("title")
    value = VALUE("hello")
    node = FIELD_EQ(field, value)
    assert node.type == "FIELD_EQ"
    assert str(node) == "title:hello"


def test_ast_field_empty():
    field = FIELD("description")
    node = FIELD_EMPTY(field)
    assert node.type == "FIELD_EQ"
    assert str(node) == "description:"


def test_ast_not():
    field = FIELD("title")
    value = VALUE("hello")
    eq_node = FIELD_EQ(field, value)

    node = NOT(eq_node)
    assert node.type == "NOT"
    assert str(node) == "NOT ( title:hello )"


def test_ast_or():
    field1 = FIELD("title")
    value1 = VALUE("hello")
    node1 = FIELD_EQ(field1, value1)

    field2 = FIELD("tags")
    value2 = VALUE("world")
    node2 = FIELD_EQ(field2, value2)

    or_node = OR(node1, node2)
    assert or_node.type == "OR"
    assert str(or_node) == "( title:hello ) OR ( tags:world )"


def test_invalid_types_raise_not_implemented():
    field = FIELD("title")
    with pytest.raises(NotImplementedError):
        FIELD_EQ(field, "string_instead_of_ast_node")  # type: ignore

    with pytest.raises(NotImplementedError):
        NOT("string_instead_of_ast_node")  # type: ignore

    with pytest.raises(NotImplementedError):
        OR(field, "string_instead_of_ast_node")  # type: ignore
