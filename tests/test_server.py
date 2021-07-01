import pytest

import shutil

from pathlib import Path

from aiohttp.test_utils import TestClient

from tiddlyserver.git import init_repo_if_needed

from tiddlyserver.server import make_app, EMPTY_WITH_TIDDLYWEB

from test_git import git_log


@pytest.fixture
def tiddler_path(tmp_path: Path) -> Path:
    path = tmp_path / "tiddlers"
    path.mkdir()
    return path

@pytest.fixture
def empty_html(tiddler_path: Path) -> Path:
    filename = tiddler_path / "tiddlers"
    shutil.copy(EMPTY_WITH_TIDDLYWEB, filename)
    return filename


class TestNoGit:

    @pytest.fixture
    async def server(self, aiohttp_client: None, tiddler_path: Path, empty_html: Path) -> TestClient:
        app = make_app(empty_html, tiddler_path, use_git=False)
        return await aiohttp_client(app)
    
    
    async def test_apis(self, server: TestClient) -> None:
        # Initially empty
        response = await server.get("/recipes/all/tiddlers.json")
        assert (await response.json()) == []
        
        # Add a tiddler
        response = await server.put(
            "/recipes/all/tiddlers/foobar",
            json={"title": "foobar", "foo": "bar", "text": "Foo, bar, init?"},
        )
        
        # Fetch it back (should now have bag and revision fields too)
        response = await server.get(
            "/recipes/all/tiddlers/foobar",
        )
        tiddler = await response.json()
        assert set(tiddler) == {"title", "foo", "text", "bag", "revision"}
        
        # Should include the tiddler
        response = await server.get("/recipes/all/tiddlers.json")
        tiddlers = await response.json()
        assert len(tiddlers) == 1
        tiddler = tiddlers[0]
        assert set(tiddler) == {"title", "foo", "bag", "revision"}
        
        # The empty HTML file should have the tiddler embedded in it too
        response = await server.get("/")
        assert "Foo, bar, init?" in (await response.text())
        
        # Delete the tiddler
        response = await server.delete("/bags/bag/tiddlers/foobar")
        assert response.ok
        response = await server.get("/recipes/all/tiddlers.json")
        assert (await response.json()) == []


class TestWithGit:

    @pytest.fixture
    async def server(self, aiohttp_client: None, tiddler_path: Path, empty_html: Path) -> TestClient:
        init_repo_if_needed(tiddler_path)
        app = make_app(empty_html, tiddler_path, use_git=True)
        return await aiohttp_client(app)
    
    async def test_apis(self, server: TestClient, tiddler_path: Path) -> None:
        # Add a tiddler
        response = await server.put(
            "/recipes/all/tiddlers/foobar",
            json={"title": "foobar"},
        )
        assert git_log(tiddler_path) == ["Updated foobar"]
        
        # Add a draft and StoryList (which should be ignored
        response = await server.put(
            "/recipes/all/tiddlers/$:/StoryList",
            json={"title": "$:/StoryList"},
        )
        response = await server.put(
            "/recipes/all/tiddlers/Draft of foo",
            json={"title": "Draft of foo", "draft.of": "foo"},
        )
        assert git_log(tiddler_path) == ["Updated foobar"]
        
        # Delete the tiddler
        response = await server.delete("/bags/bag/tiddlers/foobar")
        assert response.ok
        assert git_log(tiddler_path) == ["Updated foobar", "Deleted foobar"]
        
        response = await server.delete("/bags/bag/tiddlers/foobar")
        assert not response.ok
        assert git_log(tiddler_path) == ["Updated foobar", "Deleted foobar"]
