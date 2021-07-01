import pytest

from pathlib import Path

from subprocess import run

from tiddlyserver.git import (
    init_repo_if_needed,
    commit_files_if_changed,
)


def test_init_repo_if_needed(tmp_path: Path) -> None:
    directory = tmp_path / "repo"
    directory.mkdir()
    
    assert init_repo_if_needed(directory) is True
    assert init_repo_if_needed(directory) is False
    assert init_repo_if_needed(directory) is False


def git_status(directory: Path) -> dict[Path, str]:
    output = run(
        ["git", "status", "--porcelain"],
        cwd=directory,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    
    out = {}
    for line in output.splitlines():
        code = line[:2]
        filename = line[3:]
        out[directory / filename] = code
    
    return out

def git_log(directory: Path) -> dict[Path, str]:
    return run(
        ["git", "log", "--pretty=%s"],
        cwd=directory,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.splitlines()[::-1]


class TestCommitFilesIfNeeded:

    def test_add_and_modify_files(self, tmp_path: Path) -> None:
        directory = tmp_path / "repo"
        directory.mkdir()
        
        assert init_repo_if_needed(directory) is True
        
        file_a = directory / "file_a"
        file_a.write_text("Hello")
        file_b = directory / "file_b"
        file_b.write_text("World")
        
        assert git_status(directory) == {file_a: "??", file_b: "??"}
        
        assert commit_files_if_changed(directory, [file_a], "first commit") is True
        assert git_status(directory) == {file_b: "??"}
        assert git_log(directory) == ["first commit"]
        
        # Nothing changed
        assert commit_files_if_changed(directory, [file_a], "failed commit") is False
        assert git_status(directory) == {file_b: "??"}
        assert git_log(directory) == ["first commit"]
        
        # Changed
        file_a.write_text("Hello, world!")
        assert git_status(directory) == {file_a: " M", file_b: "??"}
        assert commit_files_if_changed(directory, [file_a], "second commit") is True
        assert git_status(directory) == {file_b: "??"}
        assert git_log(directory) == ["first commit", "second commit"]

    def test_remove_files(self, tmp_path: Path) -> None:
        directory = tmp_path / "repo"
        directory.mkdir()
        assert init_repo_if_needed(directory) is True
        
        file_a = directory / "file_a"
        file_a.write_text("Hello")
        file_b = directory / "file_b"
        file_b.write_text("World")
        file_c = directory / "file_c"
        file_c.write_text("!")
        
        assert commit_files_if_changed(directory, [file_a, file_b], "first commit") is True
        
        # Delete files
        file_b.unlink()  # In repo
        file_c.unlink()  # Not in repo
        assert commit_files_if_changed(directory, [file_b, file_c], "delete commit") is True
        assert git_status(directory) == {}
