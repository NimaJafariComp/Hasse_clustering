"""
Transparent loader for poset files.

Reads either plain `.json` or gzip-compressed `.json.gz`, returning the list of
matrices. Use this so consumers don't care how a given n was stored.

Example:
    from poset_generator.load_posets import load_posets
    mats = load_posets("posets_n7.json.gz")   # or "posets_n5.json"
"""

import gzip
import json
import os


def load_posets(path):
    """Load a list of poset matrices from a .json or .json.gz file."""
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with open(path, "r") as f:
        return json.load(f)


def find_poset_file(n, search_dirs):
    """Return the first existing posets_n{n}.json[.gz] across search_dirs, or None."""
    for d in search_dirs:
        for name in (f"posets_n{n}.json", f"posets_n{n}.json.gz"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
    return None
