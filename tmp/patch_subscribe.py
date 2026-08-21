#!/usr/bin/env python3
"""Patch subscribe.py cbor-raw branch to respect client msg_type."""
import sys, pathlib
P = pathlib.Path(sys.argv[1])
src = P.read_text()
old = '        if compression == "cbor-raw":\n            msg_type = "__AnyMsg"\n'
new = '        if compression == "cbor-raw" and not msg_type:\n            msg_type = "__AnyMsg"\n'
if old not in src:
    print("OLD not found, abort"); sys.exit(2)
P.write_text(src.replace(old, new))
print("OK patched", P)
