#!/usr/bin/env python3
"""订阅 ROS1 /voice_command，通过 WebRTC 控制 Unitree GO2。

与 xf_mic_chat_standalone 发布的字符串约定一致（std_msgs/String）：
  stand_up / lie_down / wave / come_here
  nav_cancel / nav_pause / nav_resume
  goto:<ASR原文>
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import sys
import threading
from typing import Optional

from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD
from unitree_webrtc_connect.webrtc_driver import (
    UnitreeWebRTCConnection,
    WebRTCConnectionMethod,
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("dog_voice")

ROBOT_IP = os.environ.get("UNITREE_ROBOT_IP", "192.168.123.161")
VOICE_TOPIC = os.environ.get("VOICE_COMMAND_TOPIC", "/voice_command")

# come_here：短时前进
COME_HERE_VX = 0.35
COME_HERE_SEC = 2.0


async def ensure_normal_mode(conn: UnitreeWebRTCConnection) -> None:
    log.info("Checking current motion mode...")
    response = await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["MOTION_SWITCHER"],
        {"api_id": 1001},
    )
    mode = None
    if response["data"]["header"]["status"]["code"] == 0:
        data = json.loads(response["data"]["data"])
        mode = data.get("name")
        log.info("Current motion mode: %s", mode)

    if mode != "normal":
        log.info("Switching motion mode from %s to 'normal'...", mode)
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"],
            {"api_id": 1002, "parameter": {"name": "normal"}},
        )
        await asyncio.sleep(5)


async def sport(conn: UnitreeWebRTCConnection, api_id: int, parameter=None) -> None:
    payload = {"api_id": api_id}
    if parameter is not None:
        payload["parameter"] = parameter
    await conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC["SPORT_MOD"], payload)


async def move(conn: UnitreeWebRTCConnection, x: float, y: float, z: float) -> None:
    await sport(conn, SPORT_CMD["Move"], {"x": x, "y": y, "z": z})


async def stop(conn: UnitreeWebRTCConnection) -> None:
    await sport(conn, SPORT_CMD["StopMove"])


async def handle_command(conn: UnitreeWebRTCConnection, cmd: str) -> None:
    """根据 /voice_command 字符串执行动作。"""
    text = (cmd or "").strip()
    if not text:
        return
    log.info("收到语音指令: %s", text)

    if text.startswith("goto:"):
        target = text[5:].strip()
        log.warning("goto 点位暂未实现本地导航，已忽略: %s", target)
        return

    if text == "stand_up":
        await stop(conn)
        await sport(conn, SPORT_CMD["StandUp"])
        log.info("执行 StandUp")
        return

    if text == "lie_down":
        await stop(conn)
        await sport(conn, SPORT_CMD["StandDown"])
        log.info("执行 StandDown")
        return

    if text == "wave":
        await stop(conn)
        await sport(conn, SPORT_CMD["Hello"])
        log.info("执行 Hello (wave)")
        return

    if text == "come_here":
        log.info("执行 come_here: 前进 %.1fs", COME_HERE_SEC)
        await move(conn, COME_HERE_VX, 0.0, 0.0)
        await asyncio.sleep(COME_HERE_SEC)
        await stop(conn)
        return

    if text in ("nav_cancel", "nav_pause", "nav_resume"):
        await stop(conn)
        log.info("执行 StopMove (%s)", text)
        return

    log.warning("未知指令，已忽略: %s", text)


def start_ros_subscriber(cmd_queue: "queue.Queue[Optional[str]]") -> None:
    """在后台线程跑 rospy，回调里把指令放入队列。"""
    try:
        import rospy
        from std_msgs.msg import String
    except ImportError as e:
        raise RuntimeError("无法导入 rospy/std_msgs，请先 source ROS1 环境") from e

    def on_msg(msg: String) -> None:
        data = (msg.data or "").strip()
        if data:
            cmd_queue.put(data)

    def on_shutdown() -> None:
        cmd_queue.put(None)

    rospy.init_node("dog_run_with_voice", anonymous=True, disable_signals=True)
    rospy.Subscriber(VOICE_TOPIC, String, on_msg, queue_size=10)
    rospy.on_shutdown(on_shutdown)
    log.info("已订阅 %s (std_msgs/String)", VOICE_TOPIC)
    rospy.spin()


async def command_loop(conn: UnitreeWebRTCConnection, cmd_queue: "queue.Queue[Optional[str]]") -> None:
    loop = asyncio.get_event_loop()

    def _get_cmd() -> Optional[str]:
        try:
            return cmd_queue.get(timeout=0.2)
        except queue.Empty:
            return ""  # 哨兵：超时无消息，继续等

    while True:
        cmd = await loop.run_in_executor(None, _get_cmd)
        if cmd == "":
            continue
        if cmd is None:
            log.info("收到退出信号")
            break
        try:
            await handle_command(conn, cmd)
        except Exception as e:
            log.error("执行指令失败 %r: %s", cmd, e)


async def main() -> None:
    cmd_queue: "queue.Queue[Optional[str]]" = queue.Queue()

    ros_thread = threading.Thread(
        target=start_ros_subscriber, args=(cmd_queue,), daemon=True
    )
    ros_thread.start()
    # 等 rospy 节点起来
    await asyncio.sleep(0.5)

    conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=ROBOT_IP)
    log.info("Connecting to robot at %s ...", ROBOT_IP)
    await conn.connect()
    await ensure_normal_mode(conn)
    log.info("Ready. 等待话题 %s ...", VOICE_TOPIC)

    try:
        await command_loop(conn, cmd_queue)
    finally:
        try:
            await stop(conn)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
        sys.exit(0)
