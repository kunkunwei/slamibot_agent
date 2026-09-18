#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
六麦阵列 - 在线大模型语音交互模式（去 ROS2 独立版）
Six-Mic Array - Online LLM Voice Chat (Standalone, no ROS2)

本脚本是 ROS2/xf_mic/scripts/xf_mic_chat.py 的纯 Python 等价实现：
- 不依赖 rclpy / ROS2 消息 / launch
- 唤醒事件 + 原始音频：复用同目录 serial_reader.py 的串口协议（等价 mic_serial.cpp）
- ALSA 声卡音频：内置 PyAudio 采集（等价 alsa_adapter.py）
- 在线 ASR / TTS / 星火大模型：复用 ROS2 包内 spark_api.py

功能与原 chat 节点保持一致：说出唤醒词 -> 录音(基于能量VAD/静音超时) ->
在线ASR识别 -> 星火大模型流式回复 -> 边生成边在线TTS播报；播报中再次唤醒可打断。
"""

import sys
import os

# 强制无缓冲模式（与原脚本一致，便于日志实时输出）
os.environ['PYTHONUNBUFFERED'] = '1'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

import argparse
import struct
import time
import threading
import subprocess
import queue
import re
import logging
from typing import Optional, Callable, List

from intent_router import Intent, route
from robot_cmd_publisher import RobotCmdError, RobotCmdPublisher


# ==================== 依赖路径注入 ====================
def _inject_import_paths(extra_scripts_dir: Optional[str] = None):
    """
    将本文件所在目录（用于 import serial_reader）以及 ROS2 包内 scripts 目录
    （用于 import spark_api）加入 sys.path。

    spark_api 会自行从其包相对路径加载 config/xf_config.yaml，因此把 scripts
    目录加入路径后，凭证/默认参数等都能正确读取。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)

    candidates = []
    if extra_scripts_dir:
        candidates.append(extra_scripts_dir)
    env_dir = os.environ.get('XF_MIC_SCRIPTS')
    if env_dir:
        candidates.append(env_dir)

    # 相对本仓库结构推断：Python/ 与 ROS2/ 为同级目录
    repo_root = os.path.dirname(here)
    candidates.extend([
        os.path.join(repo_root, 'ROS2', 'xf_mic', 'scripts'),
        os.path.join(repo_root, 'ROS2', 'xf_speech_ws', 'src', 'xf_mic', 'scripts'),
    ])

    for path in candidates:
        if path and os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)


# ==================== 日志封装 ====================
class _Logger:
    """模拟 ROS2 get_logger() 的 info/warn/error 接口，底层走 logging。"""

    def __init__(self, name: str):
        self._log = logging.getLogger(name)

    def info(self, msg):
        self._log.info(msg)

    def warn(self, msg):
        self._log.warning(msg)

    def warning(self, msg):
        self._log.warning(msg)

    def error(self, msg):
        self._log.error(msg)


def _setup_logging():
    """配置到 stdout；force=True 以便 rospy.init_node 抢占 handler 后可恢复。"""
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] [%(name)s] %(message)s',
        stream=sys.stdout,
        force=True,
    )


# ==================== 串口驱动（唤醒 + 原始音频） ====================
# 延迟导入：在 _inject_import_paths() 之后才可用
SerialMessageReader = None


def _import_serial_reader():
    global SerialMessageReader
    if SerialMessageReader is None:
        from serial_reader import SerialMessageReader as _SMR
        SerialMessageReader = _SMR
    return SerialMessageReader


def _build_mic_serial_driver():
    """
    动态构建 MicSerialDriver 类（继承自 serial_reader.SerialMessageReader）。
    采用工厂函数是因为基类需要先完成 sys.path 注入后才能导入。
    """
    base = _import_serial_reader()

    class MicSerialDriver(base):
        """
        六麦阵列串口驱动（无 ROS）。

        复用 SerialMessageReader 的协议实现（握手、消息解析、校验、命令下发），
        但用回调替换其打印逻辑，并提供精简读取循环（不启动键盘线程、不写 PCM 文件）。

        - on_wakeup(angle: float, beam: int, keyword: str)：收到唤醒消息时回调
        - on_audio(mono_samples: List[int])：raw 模式下，收到音频帧并提取 channel0 后回调
        """

        def __init__(self, port: str, baudrate: int = 115200,
                     raw_audio: bool = False,
                     on_wakeup: Optional[Callable[[float, int, str], None]] = None,
                     on_audio: Optional[Callable[[List[int]], None]] = None):
            super().__init__(port, baudrate, pcm_file=os.devnull)
            self.raw_audio = raw_audio
            self.on_wakeup = on_wakeup
            self.on_audio = on_audio
            self.log = _Logger('mic_serial')
            self._read_thread: Optional[threading.Thread] = None

        # ---------- 覆写消息处理为回调 ----------
        def handle_wakeup_message(self, message_data: bytes):
            """解析唤醒 JSON，提取 angle/beam/keyword 后回调。结构同 mic_serial.cpp。"""
            import json
            angle = 0.0
            beam = 0
            keyword = ''
            try:
                text_data = message_data.decode('utf-8', errors='ignore')
                msg_json = json.loads(text_data)

                content = msg_json.get('content') if isinstance(msg_json, dict) else None
                if isinstance(content, str):
                    try:
                        content = json.loads(content)
                    except Exception:
                        content = None

                if isinstance(content, dict):
                    info = content.get('info')
                    if isinstance(info, str):
                        try:
                            info = json.loads(info)
                        except Exception:
                            info = None
                    if isinstance(info, dict) and isinstance(info.get('ivw'), dict):
                        ivw = info['ivw']
                        angle = float(ivw.get('angle', angle))
                        beam = int(ivw.get('physical', beam))
                        keyword = str(ivw.get('keyword', keyword))
            except Exception as e:
                self.log.warn(f'唤醒消息解析失败: {e}')

            if self.on_wakeup is not None:
                try:
                    self.on_wakeup(angle, beam, keyword)
                except Exception as e:
                    self.log.error(f'唤醒回调异常: {e}')

        def handle_audio_data(self, message_data: bytes):
            """raw 模式：把 PCM 字节解成 int16，按每 8 个取第 1 个（channel0）后回调。"""
            if not self.raw_audio or self.on_audio is None:
                return
            try:
                sample_count = len(message_data) // 2
                if sample_count == 0:
                    return
                samples = struct.unpack(f'<{sample_count}h', message_data[:sample_count * 2])
                # 等价原 _extract_mono_from_raw：6声道+控制帧，每8个int16取第1个
                mono = [samples[i] for i in range(0, len(samples) - 7, 8)]
                if mono:
                    self.on_audio(mono)
            except Exception as e:
                self.log.error(f'音频帧解析失败: {e}')

        # ---------- 启停 ----------
        def start(self) -> bool:
            if not self.open_serial():
                return False

            # 与 launch 逻辑一致：raw 开启原始音频输出，alsa 显式关闭
            try:
                if self.raw_audio:
                    self.send_get_original_audio()
                else:
                    self.send_stop_original_audio()
            except Exception as e:
                self.log.warn(f'设置原始音频开关失败: {e}')

            self.running = True
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            self.log.info(f'串口驱动已启动: {self.port} (raw_audio={self.raw_audio})')
            return True

        def stop(self):
            self.running = False
            try:
                if self.raw_audio:
                    self.send_stop_original_audio()
            except Exception:
                pass
            if self._read_thread is not None:
                self._read_thread.join(timeout=1.0)
                self._read_thread = None
            self.close_serial()

        # ---------- 精简读取循环（无键盘线程 / 无 PCM 文件） ----------
        def _read_loop(self):
            buffer = b''
            self.log.info(f'开始监听串口 {self.port} ...')
            try:
                while self.running:
                    waiting = 0
                    try:
                        waiting = self.serial_conn.in_waiting
                    except Exception as e:
                        self.log.error(f'读取串口失败: {e}')
                        break

                    if waiting > 0:
                        buffer += self.serial_conn.read(waiting)

                        while len(buffer) >= self.HEADER_SIZE:
                            sync_pos = buffer.find(bytes([self.SYNC_HEADER]))
                            if sync_pos == -1:
                                buffer = b''
                                break
                            if sync_pos > 0:
                                buffer = buffer[sync_pos:]

                            header_info = self.parse_message_header(buffer)
                            if not header_info:
                                buffer = buffer[1:]
                                continue

                            total_len = self.HEADER_SIZE + header_info['msg_length'] + 1
                            if len(buffer) < total_len:
                                break

                            message = buffer[:total_len]
                            buffer = buffer[total_len:]

                            valid, header_info, msg_data = self.validate_message(message)
                            if not valid:
                                continue

                            msg_type = header_info['msg_type']
                            if msg_type == self.AUDIO_DATA_TYPE:
                                self.handle_audio_data(msg_data)
                            elif msg_type == self.HANDSHAKE_MSG_TYPE:
                                self.send_handshake_ack(header_info['msg_id'])
                            elif msg_type == self.WAKEUP_MSG_TYPE:
                                self.handle_wakeup_message(msg_data)
                    else:
                        time.sleep(0.005)
            except Exception as e:
                self.log.error(f'串口读取循环异常: {e}')
            finally:
                self.log.info('串口读取循环已退出')

    return MicSerialDriver


# ==================== ALSA 声卡音频采集（PyAudio） ====================
class AlsaAudioReader:
    """
    通过 PyAudio 从 ALSA 设备采集音频并以 mono int16 列表回调。
    移植自 ROS2/xf_mic/scripts/alsa_adapter.py。
    """

    def __init__(self, on_audio: Callable[[List[int]], None],
                 device_keyword: str = 'ListenGo',
                 sample_rate: int = 16000, channels: int = 1,
                 frames_per_buffer: int = 1024):
        self.on_audio = on_audio
        self.device_keyword = device_keyword
        self.sample_rate = sample_rate
        self.channels = channels
        self.frames_per_buffer = frames_per_buffer
        self.log = _Logger('alsa_adapter')

        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._pyaudio = None
        self._stream = None
        self._alsa_err_handler = None

    @staticmethod
    def _suppress_alsa_warnings():
        """抑制 ALSA 库的无关警告（仅 Linux 有效）。"""
        try:
            import ctypes
            asound = ctypes.CDLL('libasound.so.2')
            error_handler_func = ctypes.CFUNCTYPE(
                None, ctypes.c_char_p, ctypes.c_int,
                ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p
            )

            def py_error_handler(filename, line, function, err, fmt):
                pass

            c_handler = error_handler_func(py_error_handler)
            asound.snd_lib_error_set_handler(c_handler)
            return c_handler
        except Exception:
            return None

    def _find_device_by_name(self, keyword: str) -> int:
        for i in range(self._pyaudio.get_device_count()):
            info = self._pyaudio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0 and keyword.lower() in info['name'].lower():
                return i
        return -1

    def _list_all_devices(self):
        for i in range(self._pyaudio.get_device_count()):
            info = self._pyaudio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                self.log.info(f"  [{i}] {info['name']} (输入通道: {info['maxInputChannels']})")

    def start(self) -> bool:
        self._alsa_err_handler = self._suppress_alsa_warnings()
        import pyaudio

        self._pyaudio = pyaudio.PyAudio()
        device_index = self._find_device_by_name(self.device_keyword)
        if device_index < 0:
            self.log.error(f'未找到包含 "{self.device_keyword}" 的音频设备!')
            self.log.error('可用设备列表:')
            self._list_all_devices()
            return False

        info = self._pyaudio.get_device_info_by_index(device_index)
        self.log.info(f'找到设备: [{device_index}] {info["name"]}')

        try:
            self._stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.frames_per_buffer,
            )
        except Exception as e:
            self.log.error(f'打开音频流失败: {e}')
            return False

        self.running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        self.log.info('音频流已打开，开始采集...')
        return True

    def _read_loop(self):
        while self.running:
            try:
                raw_data = self._stream.read(self.frames_per_buffer, exception_on_overflow=False)
                sample_count = len(raw_data) // 2
                if sample_count == 0:
                    continue
                samples = struct.unpack(f'<{sample_count}h', raw_data[:sample_count * 2])
                self.on_audio(list(samples))
            except IOError as e:
                self.log.warn(f'读取音频流 I/O 错误: {e}')
            except Exception as e:
                self.log.error(f'读取音频时出错: {e}')
                break

    def stop(self):
        self.running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
        except Exception:
            pass
        try:
            if self._pyaudio is not None:
                self._pyaudio.terminate()
        except Exception:
            pass


# ==================== 自由对话模式（核心，去 ROS） ====================
class ChatMode:
    """
    自由对话模式（无 ROS）。
    状态机 / VAD / 流式TTS / 打断 / ASR->星火->TTS 流程与原 xf_mic_chat.py 一致。
    """

    # 状态机状态
    STATE_IDLE = 'idle'             # 等待唤醒
    STATE_LISTENING = 'listening'   # 正在录音
    STATE_PROCESSING = 'processing'  # 处理中（ASR/LLM）
    STATE_PLAYING = 'playing'       # 正在播放语音（可被打断）

    def __init__(self, spark_api_module,
                 silence_timeout: float = None, max_record_time: float = None,
                 spark_model: str = None, tts_voice: str = None,
                 audio_dir: str = None, vad_threshold: int = None,
                 debug: bool = False):
        self._api = spark_api_module
        self.log = _Logger('xf_mic_chat')
        self.debug = debug

        # 配置参数（优先使用传入参数，否则使用配置文件默认值）
        self.silence_timeout = silence_timeout if silence_timeout is not None else self._api.DEFAULT_SILENCE_TIMEOUT
        self.max_record_time = max_record_time if max_record_time is not None else self._api.DEFAULT_MAX_RECORD_TIME
        self.spark_model = spark_model or self._api.DEFAULT_SPARK_MODEL
        self.tts_voice = tts_voice or self._api.DEFAULT_TTS_VOICE
        self.audio_dir = audio_dir

        # 状态
        self.state = self.STATE_IDLE
        self.audio_buffer = []
        self.record_start_time = None
        self.last_sound_time = None

        # VAD参数（基于能量的简单VAD）
        self.vad_threshold = vad_threshold if vad_threshold is not None else 500
        self.vad_frame_count = 0
        self.peak_energy = 0.0          # 本轮录音峰值能量（用于诊断/调阈值）
        self._last_dbg_log = 0.0        # debug 能量打印节流

        # 唤醒提示音缓存（首次用在线TTS合成"我在"后存为wav，之后秒播）
        self._wakeup_cache_path = None

        # 对话历史
        self.chat_history = []
        self.system_prompt = "你是一个友好的智能助手，请用简洁的语言回答问题。回答尽量控制在80字以内。"

        # 打断相关
        self.tts_instance = None
        self.spark_instance = None
        self.interrupt_flag = False

        # 流式TTS队列
        self.tts_text_queue: Optional[queue.Queue] = None
        self.tts_worker_thread: Optional[threading.Thread] = None
        self.tts_stop_event = threading.Event()
        self.tts_device_str: Optional[str] = None

        # 会话ID（用于隔离不同对话轮次）
        self.chat_session_id = 0

        # 后台定时检查线程（取代 rclpy 定时器）
        self._running = False
        self._check_thread: Optional[threading.Thread] = None

        # 语音控狗（意图 + ROS1 /voice_command）
        cfg = self._api.get_config()
        ros_cmd = cfg.get('ros_cmd')
        intent_cfg = cfg.get('intent')
        if not isinstance(ros_cmd, dict) or not isinstance(intent_cfg, dict):
            raise RuntimeError(
                'xf_config.yaml 缺少 ros_cmd / intent 配置段，无法启动语音控狗'
            )
        topic = str(ros_cmd.get('topic') or '/voice_command')
        self.intent_cfg = intent_cfg
        self.cmd_publisher = RobotCmdPublisher(topic=topic)

        self._print_banner()

    def _print_banner(self):
        self.log.info('========================================')
        self.log.info('六麦阵列 - 在线大模型语音交互模式（独立版）')
        self.log.info('本模式强制使用在线ASR和在线TTS，配置文件中的offline设置无效')
        self.log.info(
            f'已启用语音控狗：ROS1 发布 {self.cmd_publisher.topic} (std_msgs/String)'
        )
        self.log.info('========================================')
        self.log.info('说出唤醒词后 开始对话')

    # ---------- 生命周期 ----------
    def start(self):
        """启动 ROS 发布器与后台状态检查线程（0.1s 周期，取代 rclpy 定时器）。"""
        self.cmd_publisher.start()
        # rospy.init_node 会改写 logging，恢复到 stdout，避免 ASR/意图日志消失
        _setup_logging()
        self._running = True
        self._check_thread = threading.Thread(target=self._check_loop, daemon=True)
        self._check_thread.start()

    def stop(self):
        self._running = False
        if self._check_thread is not None:
            self._check_thread.join(timeout=1.0)
            self._check_thread = None

    def _check_loop(self):
        while self._running:
            try:
                self._check_recording_state()
            except Exception as e:
                self.log.error(f'状态检查异常: {e}')
            time.sleep(0.1)

    # ---------- 声卡 / 播放 ----------
    def _find_speaker_card(self):
        """查找USB Audio声卡"""
        try:
            result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if line.startswith('card') and 'usb audio' in line.lower():
                    parts = line.split(':')
                    if parts:
                        return parts[0].strip().split()[1]
            self.log.warn('未找到USB声卡，回退到默认 card 0')
            return '0'
        except Exception as e:
            self.log.error(f'查找声卡失败: {e}')
            return '0'

    def _resolve_audio_path(self, filename: str) -> Optional[str]:
        """在可配置 audio_dir / 常见相对路径中定位音频文件。"""
        candidates = []
        if self.audio_dir:
            candidates.append(os.path.join(self.audio_dir, filename))
        here = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(here)
        candidates.extend([
            os.path.join(repo_root, 'ROS2', 'xf_mic', 'audio', filename),
            os.path.join(repo_root, 'ROS2', 'xf_speech_ws', 'src', 'xf_mic', 'audio', filename),
            os.path.join(here, 'audio', filename),
        ])
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    def _play_audio_file(self, filename: str):
        """播放音频文件；若 wav 不存在，则用在线TTS合成一次并缓存，之后秒播。"""
        try:
            # 优先使用现成 wav（如 audio/wakeup.wav）
            audio_path = self._resolve_audio_path(filename)
            # 提示音类文件：若没有现成 wav，则用缓存的合成 wav（只在首次联网合成）
            text_map = {'wakeup.wav': '我在'}
            if audio_path is None and filename in text_map:
                audio_path = self._ensure_prompt_cache(filename, text_map[filename])

            if audio_path and os.path.exists(audio_path):
                card_num = self._find_speaker_card()
                os.system(f'aplay -D plughw:{card_num},0 -q "{audio_path}"')
                return

            self.log.error(f'音频文件不存在且无法合成: {filename}')
        except Exception as e:
            self.log.error(f'播放音频失败: {e}')

    def _ensure_prompt_cache(self, filename: str, text: str) -> Optional[str]:
        """确保提示音的缓存 wav 存在（首次用在线TTS合成PCM并写成wav）。"""
        try:
            import wave
            here = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.join(here, 'audio')
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, '_cache_' + filename)

            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 44:
                return cache_path

            self.log.info(f'首次合成提示音"{text}"并缓存为 {cache_path} ...')
            tts = self._api.XfTTS()
            pcm = tts.synthesize(text=text, voice=self.tts_voice)  # 16k/mono/16bit PCM
            if not pcm:
                self.log.warn('提示音合成结果为空')
                return None
            with wave.open(cache_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(pcm)
            return cache_path
        except Exception as e:
            self.log.error(f'合成/缓存提示音失败: {e}')
            return None

    def _stop_playback(self):
        """停止当前播放（用于打断）"""
        self.interrupt_flag = True

        if self.tts_instance:
            try:
                self.tts_instance.stop()
            except Exception:
                pass
            self.tts_instance = None

        self.tts_stop_event.set()

        if self.spark_instance:
            try:
                self.spark_instance.stop()
            except Exception:
                pass

        if self.tts_text_queue:
            try:
                while not self.tts_text_queue.empty():
                    self.tts_text_queue.get_nowait()
            except Exception:
                pass

    # ---------- 唤醒 / 音频回调（取代 ROS 订阅） ----------
    def on_wakeup(self, angle: float = 0.0, beam: int = 0, keyword: str = ''):
        """唤醒事件入口（由串口驱动回调）。用独立线程处理，避免阻塞串口读取。"""
        self.log.info(f'唤醒 DOA angle={angle} beam={beam} keyword={keyword}')
        threading.Thread(target=self._wakeup_callback, daemon=True).start()

    def _wakeup_callback(self):
        """唤醒事件回调（逻辑同原 _wakeup_callback）"""
        # 如果正在播放，触发打断
        if self.state == self.STATE_PLAYING:
            self.log.info('检测到唤醒，打断播放!')
            self._stop_playback()
            time.sleep(0.2)  # 等待声卡释放
            self._play_audio_file('wakeup.wav')
            time.sleep(0.5)
            self._start_recording()
            return

        # 如果正在录音或处理中，忽略
        if self.state != self.STATE_IDLE:
            self.log.warn('正在处理中，忽略唤醒')
            return

        self.log.info('我在!')
        self._play_audio_file('wakeup.wav')
        time.sleep(0.25)
        self._start_recording()

    def _speak_text(self, text: str):
        """单句 TTS 播报（控狗反馈）；失败必须抛出，禁止静默。"""
        if not text or not str(text).strip():
            raise RuntimeError('TTS 文本为空')
        self.state = self.STATE_PLAYING
        self.interrupt_flag = False
        try:
            card_num = self._find_speaker_card()
            device_str = f'plughw:{card_num},0'
            self.tts_instance = self._api.XfTTS()
            self.tts_instance.play_text(
                text=str(text).strip(),
                device_str=device_str,
                voice=self.tts_voice,
            )
        finally:
            self.tts_instance = None
            if self.state == self.STATE_PLAYING:
                self.state = self.STATE_IDLE

    def _handle_robot_intent(self, intent: Intent) -> str:
        """执行控狗意图：发布 ROS1 字符串，返回 TTS 文案；失败抛 RobotCmdError。"""
        from robot_cmd_publisher import intent_to_command
        cmd = intent_to_command(intent)
        self.log.info(f'发布语音指令 {self.cmd_publisher.topic}: {cmd}')
        return self.cmd_publisher.publish_intent(intent)

    def on_audio(self, mono_samples: List[int]):
        """音频数据入口（由串口/ALSA 驱动回调，已为 channel0 单声道 int16）。"""
        if self.state != self.STATE_LISTENING:
            return

        self.audio_buffer.extend(mono_samples)

        # VAD：计算能量
        if mono_samples:
            energy = sum(abs(s) for s in mono_samples) / len(mono_samples)
            if energy > self.peak_energy:
                self.peak_energy = energy
            if energy > self.vad_threshold:
                self.last_sound_time = time.time()
                self.vad_frame_count = 0
            else:
                self.vad_frame_count += 1

            # 调试：周期性打印实时能量，便于判断麦克风音量与阈值是否匹配
            if self.debug:
                now = time.time()
                if now - self._last_dbg_log >= 0.3:
                    self._last_dbg_log = now
                    self.log.info(
                        f'[VAD] energy={energy:.0f} 阈值={self.vad_threshold} '
                        f'峰值={self.peak_energy:.0f} 缓冲={len(self.audio_buffer)}')

    # ---------- 录音控制 ----------
    def _start_recording(self):
        self.state = self.STATE_LISTENING
        self.audio_buffer = []
        self.record_start_time = time.time()
        self.last_sound_time = time.time()
        self.vad_frame_count = 0
        self.peak_energy = 0.0
        self.log.info('开始录音...（请在听到提示音后立即说话）')

    def _stop_recording(self):
        if self.state != self.STATE_LISTENING:
            return
        self.state = self.STATE_PROCESSING
        threading.Thread(target=self._process_audio, daemon=True).start()

    def _check_recording_state(self):
        if self.state != self.STATE_LISTENING:
            return

        now = time.time()

        # 检查最大录音时长
        if now - self.record_start_time >= self.max_record_time:
            self.log.info('达到最大录音时长')
            self._stop_recording()
            return

        # 检查静音超时
        if self.last_sound_time and (now - self.last_sound_time) >= self.silence_timeout:
            if len(self.audio_buffer) > 8000:  # 至少0.5秒
                self.log.info('检测到静音，停止录音')
                self._stop_recording()

    # ---------- 处理：ASR -> 星火 -> 流式TTS ----------
    def _process_audio(self):
        try:
            if not self.audio_buffer:
                self.log.warn('没有录制到音频数据')
                self.state = self.STATE_IDLE
                return

            # 转换为PCM字节数据
            pcm_data = struct.pack(f'<{len(self.audio_buffer)}h', *self.audio_buffer)

            # 录音统计（便于诊断麦克风音量/阈值）
            duration = len(self.audio_buffer) / 16000.0
            self.log.info(
                f'录音结束: 时长={duration:.2f}秒, 峰值能量={self.peak_energy:.0f}, '
                f'VAD阈值={self.vad_threshold}')
            if self.peak_energy < self.vad_threshold:
                self.log.warn(
                    '峰值能量低于VAD阈值，可能没采到说话声：请离麦克风近一点/说话大声一点，'
                    '或调低 --vad-threshold（如 200）')

            # 1. ASR 语音转文字
            self.log.info('正在识别语音...')
            try:
                user_text = self._api.speech_to_text(pcm_data)
                if not user_text.strip():
                    self.log.warn('未识别到有效语音')
                    self.state = self.STATE_IDLE
                    return

                self.log.info(f'>>> 问题: {user_text}')
            except Exception as e:
                self.log.error(f'语音识别失败: {e}')
                self.state = self.STATE_IDLE
                return

            # 2a. 控狗意图（规则优先）；失败明确 TTS，禁止静默
            intent = route(user_text, self.intent_cfg)
            if intent.name != 'chat':
                self.log.info(f'控狗意图: {intent.name}')
                try:
                    reply = self._handle_robot_intent(intent)
                except RobotCmdError as e:
                    reply = str(e)
                    self.log.error(f'控狗失败: {e}')
                try:
                    self._speak_text(reply)
                except Exception as e:
                    self.log.error(f'控狗反馈 TTS 失败: {e}')
                    self.state = self.STATE_IDLE
                    return
                self.log.info('等待下一次唤醒...')
                self.state = self.STATE_IDLE
                return

            # 2. 发送给Spark大模型（边生成边播放）
            self.log.info('正在思考...')

            # 准备流式TTS
            self.state = self.STATE_PLAYING
            self.interrupt_flag = False
            self.vad_frame_count = 0

            # 每次会话创建独立的Event和Queue
            local_stop_event = threading.Event()
            local_text_queue = queue.Queue()
            self.tts_stop_event = local_stop_event
            self.tts_text_queue = local_text_queue

            self.chat_session_id += 1
            current_session_id = self.chat_session_id

            card_num = self._find_speaker_card()
            self.tts_device_str = f'plughw:{card_num},0'

            # TTS Worker 线程
            def tts_worker():
                while not local_stop_event.is_set():
                    try:
                        text = local_text_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if text is None or local_stop_event.is_set():
                        break
                    if self.chat_session_id != current_session_id:
                        break
                    try:
                        self.tts_instance = self._api.XfTTS()
                        self.tts_instance.play_text(
                            text=text,
                            device_str=self.tts_device_str,
                            voice=self.tts_voice
                        )
                    except Exception as e:
                        self.log.error(f'TTS播放失败: {e}')
                    finally:
                        self.tts_instance = None

            self.tts_worker_thread = threading.Thread(target=tts_worker)
            self.tts_worker_thread.start()

            # on_token 回调
            text_buffer = []
            sentence_end_pattern = re.compile(r'[。！？.!?]')

            def on_token(token):
                if self.interrupt_flag or local_stop_event.is_set():
                    return
                if self.chat_session_id != current_session_id:
                    return
                sys.stderr.write(token)
                sys.stderr.flush()
                text_buffer.append(token)
                current_text = ''.join(text_buffer)
                if sentence_end_pattern.search(current_text):
                    if not local_stop_event.is_set():
                        local_text_queue.put(current_text)
                    text_buffer.clear()

            try:
                self.spark_instance = self._api.XfSpark(model=self.spark_model)
                ai_response = self.spark_instance.chat(
                    user_input=user_text,
                    history=self.chat_history[-10:],
                    system_prompt=self.system_prompt,
                    on_token=on_token
                )

                sys.stderr.write('\n')
                sys.stderr.flush()

                # 推送剩余buffer
                remaining = ''.join(text_buffer)
                if self.chat_session_id == current_session_id:
                    if remaining.strip() and not local_stop_event.is_set():
                        local_text_queue.put(remaining)
                    local_text_queue.put(None)  # 结束信号

                # 更新对话历史
                self.chat_history.append({"role": "user", "content": user_text})
                self.chat_history.append({"role": "assistant", "content": ai_response})

            except Exception as e:
                self.log.error(f'大模型调用失败: {e}')
                self.tts_text_queue.put(None)

            # 等待TTS播放完成
            if self.tts_worker_thread:
                self.tts_worker_thread.join()
                self.tts_worker_thread = None

            # 清理
            self.spark_instance = None
            self.tts_text_queue = None

            # 状态恢复
            if self.state == self.STATE_PLAYING:
                if self.interrupt_flag:
                    self.interrupt_flag = False
                    return
                self.log.info('等待下一次唤醒...')
                self.state = self.STATE_IDLE

        except Exception as e:
            self.log.error(f'处理音频时出错: {e}')
            self.state = self.STATE_IDLE


# ==================== 入口 ====================
def main():
    parser = argparse.ArgumentParser(description='六麦阵列 - 在线大模型语音交互模式（去 ROS2 独立版）')
    parser.add_argument('--silence-timeout', '-s', type=float, default=None,
                        help='静音超时时间（秒），默认从配置文件读取')
    parser.add_argument('--max-record-time', '-m', type=float, default=None,
                        help='最大录音时长（秒），默认从配置文件读取')
    parser.add_argument('--spark-model', '-v', default=None,
                        choices=['lite', 'pro', 'pro-128k', 'max', 'max-32k', 'ultra'],
                        help='Spark模型版本(lite/pro/max/ultra等)，默认从配置文件读取')
    parser.add_argument('--tts-voice', '-t', default=None,
                        help='TTS发音人，默认从配置文件读取')
    parser.add_argument('--audio-source', default=None,
                        choices=['alsa', 'raw'],
                        help='音频来源，默认从配置文件 audio_source 读取')
    parser.add_argument('--port', '-p', default='/dev/lg_speech_serial',
                        help='唤醒/控制串口设备路径（默认 /dev/lg_speech_serial）')
    parser.add_argument('--baudrate', '-b', type=int, default=115200,
                        help='串口波特率（默认 115200）')
    parser.add_argument('--device-keyword', default='ListenGo',
                        help='ALSA 设备名称关键词（alsa 模式用，默认 ListenGo）')
    parser.add_argument('--audio-dir', default=None,
                        help='提示音 wav 所在目录（默认自动在仓库内查找）')
    parser.add_argument('--scripts-dir', default=None,
                        help='spark_api.py 所在目录（默认自动推断 ROS2/xf_mic/scripts）')
    parser.add_argument('--vad-threshold', type=int, default=None,
                        help='VAD 能量阈值（默认 500；麦克风偏小声可调低，如 200）')
    parser.add_argument('--debug', action='store_true',
                        help='打印实时能量等调试信息，便于排查录音/识别问题')

    args, _ = parser.parse_known_args()

    _setup_logging()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    _inject_import_paths(args.scripts_dir)

    try:
        import spark_api
    except Exception as e:
        logging.getLogger('main').error(
            f'导入 spark_api 失败: {e}\n请用 --scripts-dir 指定其所在目录，'
            f'或设置环境变量 XF_MIC_SCRIPTS。')
        sys.exit(1)

    # 音频来源：命令行优先，否则跟随配置文件
    audio_source = args.audio_source or spark_api.get_config().get('audio_source', 'alsa')
    is_raw = (audio_source == 'raw')

    # VAD 阈值：命令行优先，否则跟随配置文件（vad_threshold），再否则默认
    vad_threshold = args.vad_threshold
    if vad_threshold is None:
        cfg_vad = spark_api.get_config().get('vad_threshold')
        if cfg_vad is not None:
            vad_threshold = int(cfg_vad)

    # 创建对话核心
    chat = ChatMode(
        spark_api_module=spark_api,
        silence_timeout=args.silence_timeout,
        max_record_time=args.max_record_time,
        spark_model=args.spark_model,
        tts_voice=args.tts_voice,
        audio_dir=args.audio_dir,
        vad_threshold=vad_threshold,
        debug=args.debug,
    )

    # 串口驱动（始终用于唤醒；raw 模式同时提供音频）
    MicSerialDriver = _build_mic_serial_driver()
    driver = MicSerialDriver(
        port=args.port,
        baudrate=args.baudrate,
        raw_audio=is_raw,
        on_wakeup=chat.on_wakeup,
        on_audio=(chat.on_audio if is_raw else None),
    )

    alsa_reader = None
    if not is_raw:
        alsa_reader = AlsaAudioReader(
            on_audio=chat.on_audio,
            device_keyword=args.device_keyword,
        )

    log = _Logger('main')
    log.info(f'音频来源: {audio_source}')

    chat.start()

    if not driver.start():
        log.error('串口驱动启动失败，退出')
        chat.stop()
        sys.exit(1)

    if alsa_reader is not None:
        if not alsa_reader.start():
            log.error('ALSA 音频采集启动失败，退出')
            driver.stop()
            chat.stop()
            sys.exit(1)

    try:
        while True:
            time.sleep(0.5)
    except (KeyboardInterrupt, SystemExit):
        log.info('收到退出信号，正在关闭...')
    finally:
        chat.stop()
        if alsa_reader is not None:
            alsa_reader.stop()
        driver.stop()
        log.info('已退出')


if __name__ == '__main__':
    main()
