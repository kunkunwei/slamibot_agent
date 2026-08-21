#!/usr/bin/env python3
"""Patch cbor_conversion.py: typed arrays must be plain list, not CBOR Tag."""
import pathlib
P = pathlib.Path("/tmp/cbor_conversion.py")
src = P.read_text()
old = (
    '        # numeric arrays\n'
    '        elif slot_type in TAGGED_ARRAY_FORMATS:\n'
    '            tag, fmt = TAGGED_ARRAY_FORMATS[slot_type]\n'
    '            fmt_to_length = fmt.format(len(val))\n'
    '            packed = struct.pack(fmt_to_length, *val)\n'
    '            out[slot] = Tag(tag=tag, value=packed)\n'
)
new = (
    '        # numeric arrays\n'
    '        elif slot_type in TAGGED_ARRAY_FORMATS:\n'
    '            # 2026-08-19 patch: 客户端 APP 期望 CBOR array of int，而不是\n'
    '            # IETF typed-array tag (Tag 72/77/...) 包裹的 byte string。\n'
    '            out[slot] = [int(x) for x in val]\n'
)
print("OLD found:", old in src)
P.write_text(src.replace(old, new))
