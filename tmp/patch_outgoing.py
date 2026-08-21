#!/usr/bin/env python3
"""Patch get_cbor_raw to delegate to get_cbor (cbor-raw behaves like cbor)."""
import pathlib
P = pathlib.Path("/tmp/outgoing_message.py")
src = P.read_text()
old = (
    '    def get_cbor_raw(self, outgoing_msg):\n'
    '        if self._cbor_raw_msg is None:\n'
    '            now = get_rostime()\n'
    '            outgoing_msg[u"msg"] = {\n'
    '                u"secs": now.secs,\n'
    '                u"nsecs": now.nsecs,\n'
    '                u"bytes": self._message._buff\n'
    '            }\n'
    '            self._cbor_raw_msg = encode_cbor(outgoing_msg)\n'
    '\n'
    '        return self._cbor_raw_msg\n'
)
new = (
    '    def get_cbor_raw(self, outgoing_msg):\n'
    '        # 2026-08-19 patch: client APP requests cbor-raw but parses cbor envelope.\n'
    '        # Mirror get_cbor output so downstream parser sees structured msg.\n'
    '        return self.get_cbor(outgoing_msg)\n'
)
print("OLD found:", old in src)
P.write_text(src.replace(old, new))
