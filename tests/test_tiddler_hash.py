from tiddlyserver.tiddler_hash import tiddler_hash


def test_tiddler_hash() -> None:

    a1 = {"title": "a", "foo": "bar"}
    a2 = {"foo": "bar", "title": "a"}
    b = {"title": "b"}
    
    assert tiddler_hash(a1) == tiddler_hash(a2)
    assert tiddler_hash(a1) != tiddler_hash(b)
