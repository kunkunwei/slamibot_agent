#!/usr/bin/env python3
"""Unitree 键盘遥控：WASD 运动，Q 站立，R 蹲下。"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import termios
import tty
from typing import Optional

from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD
from unitree_webrtc_connect.webrtc_driver import (
    UnitreeWebRTCConnection,
    WebRTCConnectionMethod,
)

logging.basicConfig(level=logging.FATAL)

ROBOT_IP = os.environ.get("UNITREE_ROBOT_IP", "192.168.8.181")

# 线速度 / 角速度（可按手感调大调小）
VX = 0.4
VY = 0.3
VYAW = 0.8

HELP = """
键盘控制：
  W/S  前进 / 后退
  A/D  左转 / 右转
  Q    站立 (StandUp)
  R    蹲下 (StandDown)
  空格 立即停止（松键不会自动停，须按空格）
  Esc / Ctrl+C  退出
"""


class RawTerminal:
    """终端单字符非阻塞读取。"""

    def __init__(self):
        self.fd = sys.stdin.fileno()
        self._old: Optional[list] = None

    def __enter__(self):
        self._old = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, *args):
        if self._old is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self._old)

    def getch(self) -> Optional[str]:
        import select

        r, _, _ = select.select([self.fd], [], [], 0)
        if not r:
            return None
        ch = os.read(self.fd, 1)
        if not ch:
            return None
        return ch.decode("utf-8", errors="ignore")


async def ensure_ai_mode(conn: UnitreeWebRTCConnection) -> None:
    """与能正常行走的 test_yqh 对齐：保持/切回 ai，不要强制 normal。

    终端曾记录 dog_run 把 ai→normal；在 normal 下直接 Move 易出现跺脚，
    而 test_yqh 不做模式切换（狗默认在 ai）。
    """
    print("Checking current motion mode...")
    response = await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["MOTION_SWITCHER"],
        {"api_id": 1001},
    )
    mode = None
    if response["data"]["header"]["status"]["code"] == 0:
        data = json.loads(response["data"]["data"])
        mode = data.get("name")
        print(f"Current motion mode: {mode}")

    if mode != "ai":
        print(f"Switching motion mode from {mode} to 'ai'...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"],
            {"api_id": 1002, "parameter": {"name": "ai"}},
        )
        await asyncio.sleep(5)
        print("Motion mode is now 'ai'.")


async def sport(conn: UnitreeWebRTCConnection, api_id: int, parameter=None) -> None:
    payload = {"api_id": api_id}
    if parameter is not None:
        payload["parameter"] = parameter
    await conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC["SPORT_MOD"], payload)


async def move(conn: UnitreeWebRTCConnection, x: float, y: float, z: float) -> None:
    await sport(conn, SPORT_CMD["Move"], {"x": x, "y": y, "z": z})


async def stop(conn: UnitreeWebRTCConnection) -> None:
    await sport(conn, SPORT_CMD["StopMove"])


async def keyboard_loop(conn: UnitreeWebRTCConnection) -> None:
    print(HELP)
    last_sent = (None, None, None)

    with RawTerminal() as term:
        while True:
            ch = term.getch()
            if ch is None:
                # 与 test_yqh 一致：无键不发令，靠上次 Move 保持运动；高频重发会打断步态跺脚
                await asyncio.sleep(0.05)
                continue

            key = ch.lower()
            if key in ("\x1b", "\x03"):  # Esc / Ctrl+C
                print("\n退出...")
                await stop(conn)
                return

            if key == " ":
                await stop(conn)
                last_sent = (0.0, 0.0, 0.0)
                print("停止", flush=True)
                continue

            if key == "q":
                print("站立 StandUp", flush=True)
                await stop(conn)
                await sport(conn, SPORT_CMD["StandUp"])
                last_sent = (0.0, 0.0, 0.0)
                continue

            if key == "r":
                print("蹲下 StandDown", flush=True)
                await stop(conn)
                await sport(conn, SPORT_CMD["StandDown"])
                last_sent = (0.0, 0.0, 0.0)
                continue

            if key == "w":
                cmd = (VX, 0.0, 0.0)
            elif key == "s":
                cmd = (-VX, 0.0, 0.0)
            elif key == "a":
                cmd = (0.0, 0.0, VYAW)
            elif key == "d":
                cmd = (0.0, 0.0, -VYAW)
            else:
                continue

            # 仅在速度变化时发 Move；连发同向键不再刷令
            if cmd != last_sent:
                await move(conn, *cmd)
                print(f"Move x={cmd[0]:.2f} y={cmd[1]:.2f} z={cmd[2]:.2f}", flush=True)
                last_sent = cmd


async def main() -> None:
    conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=ROBOT_IP)
    print(f"Connecting to robot at {ROBOT_IP} ...")
    await conn.connect()
    await ensure_ai_mode(conn)
    print("Ready. 使用键盘控制机器狗。")
    try:
        await keyboard_loop(conn)
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
