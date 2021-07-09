import pytest

import shutil

import json

from pathlib import Path

from flask.testing import FlaskClient

from tiddlyserver.server import create_app, EMPTY_WITH_TIDDLYWEB

from test_git import git_log


@pytest.fixture
def tiddler_path(tmp_path: Path) -> Path:
    path = tmp_path / "tiddlers"
    path.mkdir()
    return path


class TestNoGit:

    @pytest.fixture
    def client(self, tiddler_path: Path) -> FlaskClient:
        app = create_app(tiddler_path, use_git=False)
        with app.test_client() as client:
            yield client
    
    def test_apis(self, client: FlaskClient) -> None:
        # Initially empty
        response = client.get("/recipes/all/tiddlers.json").get_json()
        assert response == []
        
        # Add a tiddler
        client.put(
            "/recipes/all/tiddlers/foobar",
            data=json.dumps({"title": "foobar", "foo": "bar", "text": "Foo, bar, init?"}),
            content_type="application/json",
        )
        
        # Fetch it back (should now have bag and revision fields too)
        tiddler = client.get("/recipes/all/tiddlers/foobar").get_json()
        assert set(tiddler) == {"title", "foo", "text", "bag", "revision"}
        
        # Should include the tiddler
        tiddlers = client.get("/recipes/all/tiddlers.json").get_json()
        assert len(tiddlers) == 1
        tiddler = tiddlers[0]
        assert set(tiddler) == {"title", "foo", "bag", "revision"}
        
        # The empty HTML file should have the tiddler embedded in it too
        response = client.get("/").get_data(as_text=True)
        assert "Foo, bar, init?" in response
        
        # Delete the tiddler
        client.delete("/bags/bag/tiddlers/foobar")
        response = client.get("/recipes/all/tiddlers.json").get_json()
        assert response == []


class TestWithGit:

    @pytest.fixture
    def client(self, tiddler_path: Path) -> FlaskClient:
        app = create_app(tiddler_path, use_git=True)
        with app.test_client() as client:
            yield client
    
    def test_apis(self, client: FlaskClient, tiddler_path: Path) -> None:
        # Add a tiddler
        client.put(
            "/recipes/all/tiddlers/foobar",
            data=json.dumps({"title": "foobar"}),
            content_type="application/json",
        )
        assert git_log(tiddler_path) == ["Updated empty.html", "Updated foobar"]
        
        # Add a draft and StoryList (which should be ignored
        client.put(
            "/recipes/all/tiddlers/$:/StoryList",
            data=json.dumps({"title": "$:/StoryList"}),
            content_type="application/json",
        )
        client.put(
            "/recipes/all/tiddlers/Draft of foo",
            data=json.dumps({"title": "Draft of foo", "draft.of": "foo"}),
            content_type="application/json",
        )
        assert git_log(tiddler_path) == ["Updated empty.html", "Updated foobar"]
        
        # Delete the tiddler
        client.delete("/bags/bag/tiddlers/foobar")
        assert git_log(tiddler_path) == ["Updated empty.html", "Updated foobar", "Deleted foobar"]
        
        client.delete("/bags/bag/tiddlers/foobar")
        assert git_log(tiddler_path) == ["Updated empty.html", "Updated foobar", "Deleted foobar"]
