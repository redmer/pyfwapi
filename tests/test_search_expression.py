import pytest

from pyfwapi.errors import SearchSyntaxError
from pyfwapi.search.ast import SEASTNode
from pyfwapi.search.search_expression import SE


def test_se_init():
    # Empty init
    se = SE()
    assert se.data is None

    # Init with existing node
    node = SEASTNode(type="VALUE", args=("abc", None))
    se2 = SE(node)
    assert se2.data is not None
    assert se2.data.type == "VALUE"


def test_se_fts():
    se = SE().fts("hello")
    assert se.data is not None
    assert str(se.data) == "hello"

    se = se.fts("world")
    assert se.data.type == "AND"  # type: ignore
    assert str(se.data) == "( hello ) AND ( world )"


def test_se_empty():
    se = SE().empty("title")
    assert str(se.data) == "title:"


def test_se_eq():
    se = SE().eq("name", "photo.jpg")
    assert str(se.data) == "name:photo.jpg"

    se = SE().eq(123, 456)
    assert str(se.data) == "123:456"


def test_se_colorspace():
    se = SE().colorspace("rgb")
    assert str(se.data) == "cs:rgb"


def test_se_image_orientation():
    se = SE().image_orientation("portrait")
    assert str(se.data) == "o:portrait"


def test_se_assettype():
    se = SE().assettype("image")
    assert str(se.data) == "dt:image"


def test_se_range():
    se = SE().range("size", 100, 200)
    assert str(se.data) == "size:100~~200"


def test_se_dunder_methods():
    se1 = SE().eq("tag", "cat")
    se2 = SE().eq("tag", "dog")

    se_and = se1 & se2
    assert str(se_and.data) == "( tag:cat ) AND ( tag:dog )"

    se_or = se1 | se2
    assert str(se_or.data) == "( tag:cat ) OR ( tag:dog )"

    se_not = -se1
    assert str(se_not.data) == "NOT ( tag:cat )"


def test_se_dunder_str():
    se = SE().eq("fn", "*.png") | SE().range("ph", 500, 1024)
    assert str(se) == "( fn:*.png ) OR ( ph:500~~1024 )"

    assert str(SE()) == ""


def test_se_complex_chaining():
    se = SE().eq("status", "active").range("date", "2020-01-01", "2020-12-31")
    se = se | SE().eq("override", 1)
    se = se & ~SE().empty("required_field")

    expected = "( ( ( status:active ) AND ( date:2020-01-01~~2020-12-31 ) ) OR ( override:1 ) ) AND ( NOT ( required_field: ) )"
    assert str(se) == expected


def test_se_invalid_combination():
    with pytest.raises((SearchSyntaxError, NotImplementedError)):
        SE() | "string"  # type: ignore

    with pytest.raises((SearchSyntaxError, NotImplementedError)):
        SE() & 123  # type: ignore

    with pytest.raises((SearchSyntaxError, NotImplementedError)):
        ~SE()  # type: ignore
