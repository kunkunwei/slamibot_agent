#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D360 点云不显示 —— rosbridge 订阅复现/验收脚本（与设备镜像无关，纯客户端行为）

用途
----
1) 复现：APP 在场时，WEB 用「带类型」的方式订阅 /global_cloud_navigation 会被 rosbridge 拒绝；
2) 验收：APP 修好（订阅时带上 type）之后，本脚本应与 APP 同时运行也能持续收到点云。

依赖
----
    pip install websocket-client

用法
----
    # WEB 的订阅方式（前端 roslibjs 就是这么发的：带 messageType）
    python repro_ws_probe.py --url ws://192.168.31.164:9090 --compression cbor

    # APP 的订阅方式（cbor-raw）
    python repro_ws_probe.py --url ws://192.168.31.164:9090 --compression cbor-raw

    # 故意不带 type（APP 当前的行为，会把话题注册成通配 *，毒化所有人）
    python repro_ws_probe.py --url ws://192.168.31.164:9090 --compression cbor --no-type

    # 故意把压缩方式填进 type（现场日志里出现过 "cbor-raw is not a valid type string"）
    python repro_ws_probe.py --url ws://192.168.31.164:9090 --compression cbor-raw --type-as-compression

结果判读
--------
* PASS 收到 >=1 条点云：该订阅方式可用。
* FAIL 收到 0 条且有一条 {"op":"status","level":"error"}：订阅被拒 —— 话题已被别人以 `*` 注册。
* FAIL 收到 0 条且**没有任何回执**：订阅被接受但服务端 cbor 编码抛
  `AttributeError: 'AnyMsg' object has no attribute '_slot_types'`（话题只有通配注册时的后果）。
"""

import argparse
import json
import sys
import time

try:
    import websocket
except ImportError:
    sys.exit("缺少依赖，请先执行: pip install websocket-client")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://192.168.31.164:9090", help="rosbridge websocket 地址")
    ap.add_argument("--topic", default="/global_cloud_navigation")
    ap.add_argument("--type", default="sensor_msgs/PointCloud2", help="消息类型（正常必须带）")
    ap.add_argument("--no-type", action="store_true", help="故意不发 type 字段（复现毒化）")
    ap.add_argument("--type-as-compression", action="store_true",
                    help="故意把 compression 的值填进 type 字段（复现 invalid type string）")
    ap.add_argument("--compression", default="cbor", help="none / cbor / cbor-raw")
    ap.add_argument("--throttle", type=int, default=0, help="throttle_rate，毫秒")
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--id", default="repro-probe")
    args = ap.parse_args()

    sub = {"op": "subscribe", "id": args.id, "topic": args.topic, "queue_length": 1}
    if args.type_as_compression:
        sub["type"] = args.compression
    elif not args.no_type:
        sub["type"] = args.type
    if args.compression != "none":
        sub["compression"] = args.compression
    if args.throttle:
        sub["throttle_rate"] = args.throttle

    print("URL          :", args.url)
    print("订阅报文     :", json.dumps(sub, ensure_ascii=False))
    print("-" * 72)

    try:
        ws = websocket.create_connection(args.url, timeout=15)
    except Exception as exc:  # noqa: BLE001
        print(f"连接失败: {type(exc).__name__}: {exc}")
        return 2
    ws.send(json.dumps(sub))

    got = 0
    total = 0
    statuses = []
    t0 = time.time()
    while time.time() - t0 < args.seconds:
        try:
            msg = ws.recv()
        except Exception as exc:  # noqa: BLE001
            print(f"[{time.time()-t0:5.1f}s] 收包异常: {type(exc).__name__}: {exc}")
            break
        if isinstance(msg, str):
            try:
                payload = json.loads(msg)
            except ValueError:
                payload = {"raw": msg[:200]}
            statuses.append(payload)
            print(f"[{time.time()-t0:5.1f}s] 文本回执: {json.dumps(payload, ensure_ascii=False)[:300]}")
            continue
        got += 1
        total += len(msg)
        if got <= 2 or got % 20 == 0:
            print(f"[{time.time()-t0:5.1f}s] 点云 #{got} {len(msg)} bytes")
    try:
        ws.close()
    except Exception:  # noqa: BLE001
        pass

    print("-" * 72)
    errors = [s for s in statuses if s.get("level") == "error" or s.get("op") == "status"]
    print(f"结果: 收到 {got} 条点云, 共 {total} bytes, 耗时 {time.time()-t0:.1f}s")
    if got > 0:
        print("判定: PASS —— 该订阅方式可用")
        return 0
    if errors:
        print("判定: FAIL —— 订阅被拒绝。请对照 rosbridge 日志里的")
        print("      'Tried to register topic ... but it is already established with type *'")
        return 1
    print("判定: FAIL —— 未收到数据。注意：被拒绝时客户端**不一定**收到 status 回执，")
    print("      必须去服务端日志看 'already established with type *'。先排除「本来就没数据」：")
    print("      在设备上执行  rostopic hz /global_cloud_navigation")
    print("      若确实没有频率，说明发布侧（FAST-LIO/relay）没在跑，与订阅无关；")
    print("      若频率正常，再查服务端日志里的")
    print("      AttributeError: 'AnyMsg' object has no attribute '_slot_types'")
    print("      —— 说明该话题只有通配类型注册（有客户端不带 type 先注册了）。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
