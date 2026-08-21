#!/usr/bin/env python3
"""Verify cbor-raw /map frame structure matches APP parser expectations."""
import json, websocket, time, sys
import cbor

ws = websocket.create_connection("ws://192.168.31.135:9090", timeout=4)
ws.send(json.dumps({
    "op": "subscribe",
    "id": "verify-cbor",
    "topic": "/map",
    "type": "nav_msgs/OccupancyGrid",
    "compression": "cbor-raw",
    "queue_length": 1,
}))
ws.settimeout(6)
frames = 0
sizes = []
payload = None
for _ in range(10):
    try:
        opcode, data = ws.recv_data()
        if opcode == websocket.ABNF.OPCODE_BINARY:
            frames += 1
            sizes.append(len(data))
            if payload is None:
                payload = data
    except Exception:
        break
ws.close()
print(f"binary frames: {frames}  sizes: {sizes}")
if not payload:
    sys.exit("no payload")
print(f"first payload size: {len(payload)}")
try:
    decoded = cbor.loads(payload)
except Exception as e:
    sys.exit(f"CBOR decode failed: {e}")
print(f"top-level keys: {list(decoded.keys()) if hasattr(decoded, 'keys') else type(decoded)}")
if isinstance(decoded, dict):
    print(f"  op   = {decoded.get('op')!r}")
    print(f"  topic= {decoded.get('topic')!r}")
    msg = decoded.get('msg')
    if isinstance(msg, dict):
        print(f"  msg keys: {list(msg.keys())}")
        info = msg.get('info')
        if isinstance(info, dict):
            print(f"    info.width={info.get('width')}  info.height={info.get('height')}  resolution={info.get('resolution')}")
            origin = info.get('origin', {})
            pos = origin.get('position', {}) if isinstance(origin, dict) else {}
            print(f"    info.origin.position.x={pos.get('x') if isinstance(pos, dict) else None}")
        data_arr = msg.get('data')
        if isinstance(data_arr, list):
            print(f"    data length: {len(data_arr)}")
        elif isinstance(data_arr, (bytes, bytearray)):
            print(f"    data bytes: {len(data_arr)}")
        else:
            print(f"    data type: {type(data_arr).__name__}")
        header = msg.get('header')
        if isinstance(header, dict):
            print(f"    header keys: {list(header.keys())}")
    else:
        print(f"  msg: {msg}")
