"""Reference packet transmissions from m17-packet-encode (M17_Implementations).

  python tools/gen_packet_vectors.py path/to/m17-packet-encode > tests/packet_vectors.json
"""

import json
import os
import struct
import subprocess
import sys
import tempfile

TEXTS = ["Hi", "Exactly twenty-one ch", "Hello from libm17, a longer text message that needs several packet frames to fit in.",
         "x" * 821]

encoder = sys.argv[1]
cases = []
with tempfile.TemporaryDirectory() as tmp:
    out = os.path.join(tmp, "out.sym")
    for text in TEXTS:
        subprocess.run([encoder, "-S", "N0CALL", "-D", "@ALL", "-C", "7", "-T", text, "-f", "-o", out],
                       check=True, capture_output=True)
        data = open(out, "rb").read()
        symbols = [int(x) for x in struct.unpack(f"<{len(data) // 4}f", data)]
        cases.append({"src": "N0CALL", "dst": "@ALL", "can": 7, "text": text, "symbols": symbols})
json.dump(cases, sys.stdout, separators=(",", ":"))
