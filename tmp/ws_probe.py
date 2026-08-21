#!/usr/bin/env python3
"""Live probe: subscribe to /map via 9090 with and without CBOR; report what arrives."""
import json
import sys
import time
import websocket

URL = "ws://192.168.31.135:9090"
SUB_ID = "probe-map"
DURATION = 8


def probe(label: str, compression: str | None):
    print(f"\n=== [{label}] compression={compression!r} ===")
    ws = websocket.create_connection(URL, timeout=4)
    sub = {
        "op": "subscribe",
        "id": SUB_ID,
        "topic": "/map",
        "type": "nav_msgs/OccupancyGrid",
        "queue_length": 1,
    }
    if compression:
        sub["compression"] = compression
    ws.send(json.dumps(sub))
    deadline = time.time() + DURATION
    msgs_bin = 0
    msgs_text = 0
    sample_bin_sizes = []
    sample_text_sizes = []
    sample_text_payloads = []
    while time.time() < deadline:
        try:
            ws.settimeout(2)
            opcode, data = ws.recv_data()
        except Exception as e:
            print(f"  recv error: {e}")
            break
        if opcode == websocket.ABNF.OPCODE_BINARY:
            msgs_bin += 1
            sample_bin_sizes.append(len(data))
        elif opcode == websocket.ABNF.OPCODE_TEXT:
            msgs_text += 1
            sample_text_sizes.append(len(data))
            if len(sample_text_payloads) < 1 and len(data) < 600:
                sample_text_payloads.append(data.decode("utf-8", errors="replace")[:600])
    try:
        ws.send(json.dumps({"op": "unsubscribe", "id": SUB_ID, "topic": "/map"}))
        ws.close()
    except Exception:
        pass
    print(f"  binary frames: {msgs_bin}  sample sizes (last 5): {sample_bin_sizes[-5:]}")
    print(f"  text frames:   {msgs_text}  sample sizes (last 5): {sample_text_sizes[-5:]}")
    for p in sample_text_payloads:
        print(f"  text sample: {p}")


probe("cbor-raw", "cbor-raw")
probe("no-compression", None)
