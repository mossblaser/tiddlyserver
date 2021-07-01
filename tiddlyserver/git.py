"""
A (fairly crude) automatic mechanism to automatically track changes to tiddlers
in a directory in a Git respository.
"""

from pathlib import Path

from subprocess import run, DEVNULL


def init_repo_if_needed(directory: Path) -> bool:
    """
    If the specified directory is not a git repository (or in one), create a
    new repository in that directory.
    
    Returns True iff a new repository was initialised.
    """
    p = run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=directory,
        stdout=DEVNULL,
        stderr=DEVNULL,
    )
    if p.returncode == 0:
        # We're in a git repository, stop here
        return False
    else:
        p = run(["git", "init"], cwd=directory)
        p.check_returncode()
        return True


def commit_files_if_changed(directory: Path, filenames: list[Path], message: str) -> bool:
    """
    Commit the named files to the repository.
    
    .. warning::
    
        If any changes are already staged, these will be blindly commited too!
    """
    to_add = [f.resolve() for f in filenames if f.is_file()]
    to_remove = [f.resolve() for f in filenames if not f.is_file()]
    if to_add:
        run(
            ["git", "add", "--"] + to_add,
            cwd=directory,
            check=True,
        )
    if to_remove:
        run(
            ["git", "rm", "--ignore-unmatch", "--"] + to_remove,
            cwd=directory,
            check=True,
        )
    
    changes_to_commit = run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=directory,
        capture_output=True,
        check=True,
        text=True,
    ).stdout != ""
    
    if changes_to_commit:
        run(
            ["git", "commit", "--quiet", "--message", message],
            cwd=directory,
            check=True,
        )
        return True
    else:
        return False
