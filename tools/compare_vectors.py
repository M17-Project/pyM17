"""Show which entries of regenerated test vectors differ from the committed ones (used by CI)."""

import json
import subprocess

for name in ("tests/vectors.json", "tests/crypto_vectors.json"):
    new = json.load(open(name))
    old = json.loads(subprocess.run(["git", "show", f"HEAD:{name}"], capture_output=True, check=True).stdout)
    for key in sorted(set(new) | set(old)):
        if new.get(key) != old.get(key):
            a, b = old.get(key), new.get(key)
            detail = ""
            if isinstance(a, list) and isinstance(b, list):
                idx = [i for i, (x, y) in enumerate(zip(a, b, strict=False)) if x != y]
                detail = f", {len(idx)} of {len(a)} items differ, first {idx[:5]}, lengths {len(a)} / {len(b)}"
            print(f"::error::{name}: '{key}' differs{detail}")
