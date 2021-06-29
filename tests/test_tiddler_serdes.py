import pytest

from pathlib import Path

from tiddlyserver.tiddler_serdes import (
    title_to_filename_stub,
    is_tid_safe,
    serialise_tid,
    deserialise_tid,
    serialise_json_plus_text,
    deserialise_json_plus_text,
    delete_tiddler,
    write_tiddler,
    read_tiddler,
    read_all_tiddlers,
)

class TestTitleToFilenameStub:

    @pytest.mark.parametrize(
        "title, exp_without_hash",
        [
            # Empty
            ("", ""),
            # No substitutions required
            ("foo", "foo"),
            ("foo-1 bar_", "foo-1 bar_"),
            # Universal directory separators
            ("foo/bar", "foo/bar"),
            ("foo\\bar", "foo/bar"),
            # Special characters replaced with _
            ("oh?dear.me", "oh_dear_me"),
            # Runs of special characters collapsed
            ("oh:?!dear", "oh_dear"),
            # $: is treated specially *only* in first path part
            ("$:/foo/bar", "system/foo/bar"),
            ("$:nope/foo/bar", "_nope/foo/bar"),
            ("nope/$:/foo/bar", "nope/_/foo/bar"),
            # Windows reserved names (if only part of a path)
            ("windows/is/a/con", "windows/is/a/con_"),
            ("windows/is/a/cOn", "windows/is/a/cOn_"),
            ("windows/dot/con/yep", "windows/dot/con_/yep"),
            ("windows/dot/com1/yep", "windows/dot/com1_/yep"),
            # Leading/trailing whitespace removed
            (" so / many / spaces on the outside ", "so/many/spaces on the outside"),
            # Empty path segments removed
            ("double//slash", "double/slash"),
            ("double/ /slash", "double/slash"),
            # Empty filename adpots parent directory name
            ("foo/", "foo"),
        ],
    )
    def test_substitutions(self, title: str, exp_without_hash: str) -> None:
        path = title_to_filename_stub(title)
        
        actual = "/".join(path.parts)
        if actual[-8: -7] == "_":
            actual = actual[:-8]
        else:
            actual = actual[:-7]

        assert actual == exp_without_hash
    
    
    def test_case_insensitivity_support(self) -> None:
        assert (
            str(title_to_filename_stub("foo")).lower()
            != str(title_to_filename_stub("FOO")).lower()
        )


@pytest.mark.parametrize(
    "tiddler, exp",
    [
        ({}, True),
        ({"foo": "bar"}, True),
        ({"foo": "$ bar ([<baz>]) 1_234.5?!"}, True),
        # Not tid-safe if have trailing whitespace
        ({"foo": " bar"}, False),
        ({"foo": "bar "}, False),
        # Not tid-safe if have embedded newlines
        ({"foo": "bar\nbaz"}, False),
        # Not tid-safe if have other exciting characters
        ({"foo": "bar\0baz"}, False),
        # Also check about field names!
        ({" foo ": "bar"}, False),
        # But don't care about whatever is in text field
        ({"text": " foo\nbar\0! "}, True),
        
    ],
)
def test_is_tid_safe(tiddler: dict[str, str], exp: bool) -> None:
    assert is_tid_safe(tiddler) is exp


def test_serialise_tid_and_deserialise_tid(tmp_path: Path) -> None:
    path = tmp_path / "test.tid"
    
    tiddler = {
        "title": "Test",
        "foo": "bar baz qux",
        "text": "\n foo\nbar \n",
    }
    
    serialise_tid(tiddler, path)
    assert deserialise_tid(path) == tiddler
    
    tiddler_no_text = tiddler.copy()
    del tiddler_no_text["text"]
    assert deserialise_tid(path, include_text=False) == tiddler_no_text


def test_serialise_json_plus_text_and_deserialise_json_plus_text(tmp_path: Path) -> None:
    path = tmp_path / "test.tid"
    
    tiddler = {
        "title": "Test",
        "foo": "bar\nbaz",
        "text": "\n foo\nbar \n",
    }
    
    serialise_json_plus_text(tiddler, path)
    assert deserialise_json_plus_text(path) == tiddler
    
    tiddler_no_text = tiddler.copy()
    del tiddler_no_text["text"]
    assert deserialise_json_plus_text(path, include_text=False) == tiddler_no_text


class TestReadWriteAndDeleteTiddler:
    
    def test_write_tiddler(self, tmp_path: Path) -> None:
        directory = tmp_path / "tiddlers"
        directory.mkdir()
        
        # New file
        files = write_tiddler(directory, {"title": "foo/bar", "foo": "bar", "text": "baz"})
        assert len(files) == 1
        assert sorted(files) == sorted(directory.glob("**/*.*"))
        assert deserialise_tid(files[0])["foo"] == "bar"
        
        # Overwrite file
        files2 = write_tiddler(directory, {"title": "foo/bar", "foo": "qux", "text": "baz"})
        assert sorted(files) == sorted(files2)
        assert deserialise_tid(files2[0])["foo"] == "qux"
        
        # Overwrite with different format file
        files3 = write_tiddler(directory, {"title": "foo/bar", "foo": " quo ", "text": "baz"})
        assert len(files3) == 3
        assert files[0] in files3
        assert not files[0].is_file()
        assert sorted([f for f in files3 if f != files[0]]) == sorted(directory.glob("**/*.*"))
        assert deserialise_json_plus_text(sorted(files3)[0])["foo"] == " quo "
    
    def test_read_tiddler(self, tmp_path: Path) -> None:
        directory = tmp_path / "tiddlers"
        directory.mkdir()
        
        tid_tiddler = {"title": "A .tid tiddler.", "text": "Hello"}
        json_tiddler = {"title": "A .json tiddler.", "foo": " bar ", "text": "Hello"}
        
        write_tiddler(directory, tid_tiddler)
        write_tiddler(directory, json_tiddler)
        
        assert read_tiddler(directory, tid_tiddler["title"]) == tid_tiddler
        assert read_tiddler(directory, json_tiddler["title"]) == json_tiddler
    
    def test_delete_tiddler(self, tmp_path: Path) -> None:
        directory = tmp_path / "tiddlers"
        directory.mkdir()
        
        tid_tiddler = {"title": "A .tid tiddler.", "text": "Hello"}
        json_tiddler = {"title": "A .json tiddler.", "foo": " bar ", "text": "Hello"}
        
        write_tiddler(directory, tid_tiddler)
        write_tiddler(directory, json_tiddler)
        
        assert len(list(directory.glob("**/*.*"))) == 3
        
        assert len(delete_tiddler(directory, tid_tiddler["title"])) == 1
        assert len(delete_tiddler(directory, json_tiddler["title"])) == 2
        
        assert len(list(directory.glob("**/*.*"))) == 0
    
    def test_read_all_tiddlers(self, tmp_path: Path) -> None:
        directory = tmp_path / "tiddlers"
        directory.mkdir()
        
        tid_tiddler = {"title": "A .tid tiddler.", "text": "Hello"}
        json_tiddler = {"title": "A .json tiddler.", "foo": " bar ", "text": "Hello"}
        
        write_tiddler(directory, tid_tiddler)
        write_tiddler(directory, json_tiddler)
        
        tiddlers = sorted(read_all_tiddlers(directory), key=lambda t: t["title"])
        
        assert tiddlers == [json_tiddler, tid_tiddler]
