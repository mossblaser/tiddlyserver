"""
An :py:mod:`aiohttp` based webserver implementing (a bare-bones subset of) the
TiddlyWeb API.
"""

import argparse

import inspect

import shutil

from pathlib import Path

from aiohttp import web

import tiddlyserver

from tiddlyserver.tiddler_serdes import (
    read_all_tiddlers,
    read_tiddler,
    write_tiddler,
    delete_tiddler,
)

from tiddlyserver.tiddler_embedding import embed_tiddlers_into_empty_html

from tiddlyserver.tiddler_hash import tiddler_hash

from tiddlyserver.git import (
    init_repo_if_needed,
    commit_files_if_changed,
)

EMPTY_WITH_TIDDLYWEB = Path(inspect.getfile(tiddlyserver)).parent / "empty_with_tiddlyweb.html"


routes = web.RouteTableDef()


def tiddler_git_filter(tiddler: dict[str, str]) -> bool:
    """
    Return True only for Tiddlers which should be included in Git.
    """
    return (
        # Ignore drafts
        tiddler.get("draft.of", None) is None
        # Skip the storylist
        and tiddler.get("title") != "$:/StoryList"
        # Allow manual override
        and tiddler.get("tiddlyserver.git") != "no"
    )


@routes.get('/')
async def get_index(request):
    """
    Return a copy of the empty.html with all tiddlers in the tiddler directory
    pre-loaded.
    """
    empty_html_filename: Path = request.app["empty_html_filename"]
    tiddler_dir: Path = request.app["tiddler_dir"]
    
    empty_html = empty_html_filename.read_text()
    
    tiddlers = sorted(
        read_all_tiddlers(tiddler_dir),
        key=lambda t: t.get("title", ""),
    )
    
    html = embed_tiddlers_into_empty_html(empty_html, tiddlers)
    
    return web.Response(text=html, content_type="text/html")


@routes.get('/status')
async def get_status(request):
    """
    Bare-minimum response which minimises UI cruft like usernames and login
    screens.
    """
    return web.json_response(
        {
            "space": {"recipe": "all"},
            "username": "GUEST",
            "read_only": False,
            "anonymous": True,
        }
    )


@routes.get('/recipes/all/tiddlers.json')
async def get_skinny_tiddlers(request):
    """
    Return the JSON-ified non-text fields of all local tiddler files.
    
    NB: We don't emulate the slightly quirky TiddlyWeb JSON format here since
    the TiddlyWiki implementation will cope just fine with a plain JSON object
    describing a tiddler's fields.
    """
    tiddler_dir = request.app["tiddler_dir"]
    skinny_tiddlers = list(read_all_tiddlers(tiddler_dir, include_text=False))
    return web.json_response(skinny_tiddlers)


@routes.get('/recipes/all/tiddlers/{path:.*}')
async def get_tiddler(request):
    """
    Read a tiddler.
    
    NB: We assume the 'all' space (reported by the /status endpoint).
    
    NB: We don't emulate the slightly quirky TiddlyWeb JSON format here since
    the TiddlyWiki implementation will cope just fine with a plain JSON object
    describing a tiddler's fields.
    """
    tiddler_dir = request.app["tiddler_dir"]
    title = request.match_info["path"]
    
    try:
        return web.json_response(read_tiddler(tiddler_dir, title))
    except FileNotFoundError:
        raise web.HTTPNotFound()

@routes.put('/recipes/all/tiddlers/{path:.*}')
async def put_tiddler(request):
    """
    Store (or modify) a tiddler.
    """
    tiddler_dir = request.app["tiddler_dir"]
    use_git = request.app["use_git"]
    
    title = request.match_info["path"]
    tiddler = await request.json()
    
    # Undo silly TiddlyWeb formatting
    tiddler.update(tiddler.pop("fields", {}))
    if "tags" in tiddler:
        tiddler["tags"] = " ".join(f"[[{tag}]]" for tag in tiddler.get("tags", []))
    
    # Mandatory for TiddlyWeb but (but unused by this implementation)
    tiddler["bag"] = "bag"
    
    # Set revision to hash of Tiddler contents
    tiddler.pop("revision", None)
    hash = tiddler_hash(tiddler)
    tiddler["revision"] = revision = hash
    
    # Sanity check
    assert title == tiddler.get("title")
    
    changed_files = write_tiddler(tiddler_dir, tiddler)
    if use_git and tiddler_git_filter(tiddler):
        commit_files_if_changed(tiddler_dir, changed_files, f"Updated {title}")
    
    etag = f'"bag/{title}/{revision}:{hash}"'
    
    return web.Response(
        headers={"Etag": etag},
        status=204,
    )

@routes.delete('/bags/bag/tiddlers/{path:.*}')
async def remove_tiddler(request):
    """
    Delete a tiddler.
    """
    tiddler_dir = request.app["tiddler_dir"]
    use_git = request.app["use_git"]
    
    title = request.match_info["path"]
    
    deleted_files = delete_tiddler(tiddler_dir, title)
    
    if use_git:
        commit_files_if_changed(tiddler_dir, deleted_files, f"Deleted {title}")
    
    if deleted_files:
        return web.Response()
    else:
        raise web.HTTPNotFound()


def make_app(empty_html_filename: Path, tiddler_dir: Path, use_git: bool) -> web.Application:
    """
    Create an :py:class:`aiohttp.web.Application` for the TiddlyServer.
    
    Parameters
    ==========
    empty_html_filename : Path
        An empty TiddlyWiki HTML file with nothing but the TiddlyWeb plugin
        installed.
    tiddler_dir : Path
        The directory in which tiddlers will be stored.
    use_git : bool
        If True, will ensure the tiddler directory is a git repository and
        auto-commit changes to that repository.
    """
    app = web.Application(client_max_size=1024*1024*1024)
    app.add_routes(routes)
    app["empty_html_filename"] = empty_html_filename
    app["tiddler_dir"] = tiddler_dir.resolve()
    app["use_git"] = use_git
    return app



def main():
    parser = argparse.ArgumentParser(
        description="""
            A personal (i.e. unauthenticated) server for TiddlyWiki which
            implements the TiddlyWeb protocol.
        """
    )
    
    parser.add_argument(
        "tiddler_dir",
        nargs="?",
        type=Path,
        default=Path(),
        help="""
            The directory to store all tiddlers. Defaults to the current
            working directory. In addition to the wiki, this directory must
            also contain a file called `empty.html` containing an *empty*
            TiddlyWiki with the nothing more than the TiddlyWeb plugin
            installed. If no such file exists, a suitable wiki will be copied
            automatically.
        """
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="""
            The host/IP for the server to listen on. Defaults to $(default)s.
        """
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="""
            The port to listen on. Defaults to %(default)d.
        """
    )
    
    parser.add_argument(
        "--no-git", "-G",
        action="store_true",
        default=False,
        help="""
            If given, do not track changes to tiddlers using git.
        """
    )
    
    args = parser.parse_args()
    
    tiddler_dir = args.tiddler_dir
    empty_html_filename = tiddler_dir / "empty.html"
    use_git = not args.no_git
    
    # Create tiddler directory and empty HTML if either doesn't exist yet
    if not tiddler_dir.is_dir():
        tiddler_dir.mkdir(parents=True)
    if not empty_html_filename.is_file():
        shutil.copy(
            EMPTY_WITH_TIDDLYWEB,
            empty_html_filename,
        )
    if use_git:
        init_repo_if_needed(tiddler_dir)
        commit_files_if_changed(tiddler_dir, [empty_html_filename], "Update empty.html")
    
    app = make_app(empty_html_filename, tiddler_dir, use_git)
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
