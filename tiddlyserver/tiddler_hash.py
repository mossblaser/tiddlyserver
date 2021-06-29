"""
Compute a hash of a tiddler's contents.
"""

from hashlib import md5


def tiddler_hash(tiddler: dict[str, str]) -> str:
    """
    Compute a hash of the contents of a Tiddler.
    
    This hash is the MD5 sum of the concatenated (binary) MD5 checksums of each
    UTF-8 encoded field and value in turn, in alphabetical order.
    """
    md5_sum = md5()
    for field, value in sorted(tiddler.items()):
        md5_sum.update(md5(field.encode("utf-8")).digest())
        md5_sum.update(md5(value.encode("utf-8")).digest())
    return md5_sum.hexdigest()
