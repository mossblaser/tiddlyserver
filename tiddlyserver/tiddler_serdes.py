"""
Routines for serialising and deserialising tiddlers on disk.
"""

from typing import TextIO, Iterable

import re

import json

from string import ascii_letters, digits, punctuation

from pathlib import Path

from hashlib import md5

from itertools import chain


def title_to_filename_stub(title: str) -> Path:
    """
    Convert a title into a safe filename.
    
    To make a filename safe, the following steps are taken:
    
    * The prefix "$:" is replaced with "system"
    * The title is split at all forward or backward slashes into directories.
    * Loading and trailing whitespace are removed from all path parts
    * Empty path components are removed.
    * Any path components which contain a Windows reserved filename (e.g. COM)
      are suffixed with an underscore.
    * All non alphanumeric, space, dash and underscore characters are
      replaced with ``_``.
    * The first seven (lower-case) characters of the MD5 hash of the original
      title encoded as UTF-8 are appended (after an underscore) to the end of
      the filename.
    
    No extension is added but one *must* be added to all filenames to prevent
    the possibility of clashes between directory and filenames.
    
    The initial steps of this renaming process ensure that the filename is safe
    on popular operating systems. The final step ensures that filenames are
    distinct even when some letters have been replaced (and that case changes
    result in a distinct filename.
    """
    # Split on any slash
    parts = re.split(r"[/\\]+", title)
    
    # Special case: replace $: with system
    if parts[0] == "$:":
        parts[0] = "system"
    
    # Replace all (runs of) nontrivial characters with _
    parts = [
        re.sub(r"[^a-zA-Z0-9 _-]+", "_", part)
        for part in parts
    ]
    
    # Suffix all reserved Windows filenames with _
    parts = [
        re.sub(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$", r"\1_", part, flags=re.IGNORECASE)
        for part in parts
    ]
    
    # Remove trailing whitespace (and remove any empty path components)
    parts = [part.strip() for part in parts if part.strip()]
    if not parts:
        parts.append("")
    
    # Append hash
    title_hash = md5(title.encode("utf-8")).hexdigest()[:7].lower()
    parts[-1] = f"{parts[-1]}_{title_hash}".lstrip("_")
    
    return Path(*parts)


tid_safe_characters = ascii_letters + digits + punctuation + " "
tid_safe_characters_re = re.compile(
    "(" + "|".join(re.escape(c) for c in tid_safe_characters) + ")*"
)


def is_tid_safe(tiddler: dict[str, str]) -> bool:
    """
    Check whether a tiddler has any fields which cannot be represented within a
    *.tid format file.
    """
    for field, value in tiddler.items():
        if field != "text":
            for string in [field, value]:
                # Cannot cope with trailing whitespace
                if string.strip() != string:
                    return False
                
                # Check for unsupported characters (e.g. newlines)
                if not tid_safe_characters_re.fullmatch(string):
                    return False
    
    return True


def serialise_tid(tiddler: dict[str, str], filename: Path) -> None:
    """
    Serialise a tiddler into a .tid file.
    """
    with filename.open("w", encoding="utf-8") as f:
        for field, value in sorted(tiddler.items()):
            if field != "text":
                f.write(f"{field}: {value}\n")
        f.write("\n")
        f.write(tiddler.get("text", ""))


def deserialise_tid(filename: Path, include_text: bool = True) -> dict[str, str]:
    """
    Deserialise a tiddler from a .tid file.
    """
    tiddler = {}
    with filename.open("r", encoding="utf-8") as f:
        for line in f:
            field, colon, value = line.partition(":")
            if colon:
                tiddler[field.strip()] = value.strip()
            else:
                break
        
        if include_text:
            tiddler["text"] = f.read()
        
        return tiddler


def serialise_json_plus_text(tiddler: dict[str, str], filename: Path) -> None:
    """
    Serialise a tiddler into a .json and .text file. The `.json` filename must
    be given as the argument.
    """
    tiddler = tiddler.copy()
    with filename.with_suffix(".text").open("w", encoding="utf-8") as f:
        f.write(tiddler.pop("text", ""))
    with filename.open("w", encoding="utf-8") as f:
        json.dump(tiddler, f)


def deserialise_json_plus_text(filename: Path, include_text: bool = True) -> dict[str, str]:
    """
    Deserialise a tiddler from a .json and .text file. The `.json` filename must
    be given as the argument.
    """
    tiddler = {}
    if include_text:
        with filename.with_suffix(".text").open("r", encoding="utf-8") as f:
            tiddler["text"] = f.read()
    with filename.open("r", encoding="utf-8") as f:
        tiddler.update(json.load(f))
    return tiddler


def delete_tiddler(directory: Path, title: str) -> list[Path]:
    """
    Delete the tiddler file(s) associated with the named tiddler, if it exists.
    
    Returns the full filenames of any deleted files.
    """
    out = []
    
    filename_stub = directory / title_to_filename_stub(title)
    for suffix in [".tid", ".json", ".text"]:
        filename = filename_stub.with_suffix(suffix)
        if filename.is_file():
            out.append(filename)
            filename.unlink()
    
    return out


def write_tiddler(directory: Path, tiddler: dict[str, str]) -> list[Path]:
    """
    Store the given tiddler, replacing any previously existing tiddler file.
    
    Returns the full filenames of any deleted or created files.
    """
    # Delete any previous tiddler (we delete rather than overwriting because
    # changing the tiddler may change whether it is stored in a single tid file
    # or in json+text files.
    title = tiddler.get("title", "")
    out = delete_tiddler(directory, title)
    
    filename_stub = directory / title_to_filename_stub(title)
    
    filename_stub.parent.mkdir(parents=True, exist_ok=True)
    
    if is_tid_safe(tiddler):
        filename = filename_stub.with_suffix(".tid")
        serialise_tid(tiddler, filename)
        if filename not in out:
            out.append(filename)
    else:
        json_filename = filename_stub.with_suffix(".json")
        text_filename = filename_stub.with_suffix(".text")
        
        serialise_json_plus_text(tiddler, json_filename)
        
        if json_filename not in out:
            out.append(json_filename)
        
        if text_filename not in out:
            out.append(text_filename)
    
    return out


def read_tiddler(directory: Path, title: str) -> dict[str, str]:
    """
    Read the tiddler with the title given.
    
    Raises a :py:exc:`FileNotFoundError` if the tiddler does not exist.
    """
    filename_stub = directory / title_to_filename_stub(title)

    tid_filename = filename_stub.with_suffix(".tid")
    if tid_filename.is_file():
        return deserialise_tid(tid_filename)
    
    json_filename = filename_stub.with_suffix(".json")
    if json_filename.is_file():
        return deserialise_json_plus_text(json_filename)
    
    raise FileNotFoundError(f"No .tid or .json file could be found for tiddler '{title}'")


def read_all_tiddlers(directory: Path, include_text: bool = True) -> Iterable[dict[str, str]]:
    """
    Read all of the tiddlers in the named directory.
    """
    for tid_filename in directory.glob("**/*.tid"):
        yield deserialise_tid(tid_filename, include_text)
    for json_filename in directory.glob("**/*.json"):
        yield deserialise_json_plus_text(json_filename, include_text)
