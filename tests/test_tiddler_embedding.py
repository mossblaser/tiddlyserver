import pytest

from typing import Iterable

from tiddlyserver.tiddler_embedding import (
    HTMLTagOffsetFinder,
    modify_string,
    serialise_as_text_tiddler,
    embed_tiddlers_into_empty_html,
)

class TestHTMLTagOffsetFinder:
    
    @pytest.mark.parametrize(
        "string, exp",
        [
            # Empty string
            ("", [0]),
            # Single line
            ("x", [0]),
            ("hello!", [0]),
            # Multiple lines
            ("abc\ndef", [0, 4]),
            ("abc\ndef\nghi", [0, 4, 8]),
            # Consecutive newlines
            ("abc\n\ndef", [0, 4, 5]),
            # Trailing newline
            ("abc\n", [0, 4]),
            # Leading newline
            ("\nabc", [0, 1]),
        ],
    )
    def test_lineno_to_offset(self, string: str, exp: list[int]) -> None:
        # Feed all at once
        finder = HTMLTagOffsetFinder([])
        finder.feed(string)
        assert finder._lineno_to_offset == exp
        
        # Feed one char at a time
        finder = HTMLTagOffsetFinder([])
        for c in string:
            finder.feed(c)
        assert finder._lineno_to_offset == exp

    def test_match_offsets(self) -> None:
        finder = HTMLTagOffsetFinder([("div", {})])
        string = "<div\n foo=bar> hello\nworld </div>"
        finder.feed(string)
        
        (((tag, attrs, start, end), ), ) = finder.matches
        assert tag == "div"
        assert attrs == {"foo": "bar"}
        assert string[start:end] == " hello\nworld "

    def test_mismatched_tags(self) -> None:
        finder = HTMLTagOffsetFinder([("ul", {})])
        string = "<ul><li>hello<li>world</ul>"
        finder.feed(string)
        
        (((tag, attrs, start, end), ), ) = finder.matches
        assert tag == "ul"
        assert attrs == {}
        assert string[start:end] == "<li>hello<li>world"

    def test_matching(self) -> None:
        finder = HTMLTagOffsetFinder([
            ("div", {}),
            ("div", {"foo": "bar", "baz": "qux"}),
        ])
        string = """
            <div>one</div>
            <div foo=bar>two</div>
            <div foo=bar baz=qux>three</div>
            <div foo=bar baz=qux quo=qac>four</div>
        """
        finder.feed(string)
        
        assert len(finder.matches) == 2
        assert len(finder.matches[0]) == 4
        assert len(finder.matches[1]) == 2

        matched_strings = [
            string[start:end]
            for _tag, _attrs, start, end in finder.matches[0]
        ]
        assert matched_strings == ["one", "two", "three", "four"]
        
        matched_strings = [
            string[start:end]
            for _tag, _attrs, start, end in finder.matches[1]
        ]
        assert matched_strings == ["three", "four"]


@pytest.mark.parametrize(
    "string, insertions, deletions, exp",
    [
        # Nothing to do
        ("", [], [], ""),
        ("foobar", [], [], "foobar"),
        # Insert into empty
        ("", [(0, "foo")], [], "foo"),
        # Insert into non-empty
        ("foo", [(0, "!")], [], "!foo"),
        ("foo", [(3, "!")], [], "foo!"),
        ("foo", [(1, "!")], [], "f!oo"),
        # Many insertions (not in order)
        ("foo", [(0, "0"), (3, "3"), (1, "1")], [], "0f1oo3"),
        # Multiple insertions to same index
        ("foo", [(1, "1"), (1, "2"), (1, "3")], [], "f123oo"),
        # Simple deletion
        ("abcd", [], [(1, 2)], "acd"),
        ("abcd", [], [(1, 2), (2, 3)], "ad"),
        ("abcd", [], [(1, 3)], "ad"),
        # Deletion at ends of string
        ("abcd", [], [(0, 1)], "bcd"),
        ("abcd", [], [(3, 4)], "abc"),
        ("abcd", [], [(0, 4)], ""),
        # Combined deletion and insertion
        ("abcde", [(1, "<"), (4, ">")], [(1, 4)], "a<>e"),
    ],
)
def test_modify_string(
    string: str,
    insertions: list[tuple[int, str]],
    deletions: list[tuple[int, int]],
    exp: str,
) -> None:
    assert modify_string(string, insertions, deletions) == exp


def test_serialise_as_text_tiddler() -> None:
    assert serialise_as_text_tiddler({
        "title": "Hello",
        "escape-me": '"quotes"',
        "text": 'you "&" me',
    }) == '<div title="Hello" escape-me="&quot;quotes&quot;"><pre>you "&amp;" me</pre></div>'


def test_embed_tiddlers_into_empty_html() -> None:
    html_in = """
        <html>
            <head>
                <title>Default title here...</title>
            </head>
            <body>
                <noscript>Default noscript content here</noscript>
                <div id="storeArea">
                    <div title="Existing Tiddler"><pre>Hello</pre></div>
                </div>
            </body>
        </html>
    """
    tiddlers = [
        {"title": "$:/SiteTitle", "text": "Hello"},
        {"title": "$:/SiteSubtitle", "text": "World"},
        {"title": "foo", "text": "bar"},
    ]
    html_out = embed_tiddlers_into_empty_html(html_in, tiddlers)
    
    assert html_out == """
        <html>
            <head>
                <title>Hello \N{EM DASH} World</title>
            </head>
            <body>
                <noscript>Please enable Javascript</noscript>
                <div id="storeArea">
                    <div title="Existing Tiddler"><pre>Hello</pre></div>
                <div title="$:/SiteSubtitle"><pre>World</pre></div>
<div title="$:/SiteTitle"><pre>Hello</pre></div>
<div title="foo"><pre>bar</pre></div></div>
            </body>
        </html>
    """
