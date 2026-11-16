"""Show which entries of regenerated test vectors differ from the committed ones (used by CI).

Prints GitHub error annotations, down to the first differing values of a few cases.
"""

import json
import subprocess


def describe(old, new, path, out, limit=6):
    """Collect up to ``limit`` differing leaf values below ``path``."""
    if len(out) >= limit:
        return
    if isinstance(old, dict) and isinstance(new, dict):
        for k in sorted(set(old) | set(new)):
            describe(old.get(k), new.get(k), f"{path}.{k}", out, limit)
    elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        for i, (a, b) in enumerate(zip(old, new, strict=True)):
            describe(a, b, f"{path}[{i}]", out, limit)
    elif old != new:
        out.append(f"{path}: committed {old!r:.60} regenerated {new!r:.60}")


for name in ("tests/vectors.json", "tests/crypto_vectors.json"):
    new = json.load(open(name))
    old = json.loads(subprocess.run(["git", "show", f"HEAD:{name}"], capture_output=True, check=True).stdout)
    for key in sorted(set(new) | set(old)):
        if new.get(key) != old.get(key):
            diffs: list[str] = []
            describe(old.get(key), new.get(key), key, diffs)
            print(f"::error::{name}: '{key}' differs")
            for d in diffs:
                print(f"::error::{d}")
