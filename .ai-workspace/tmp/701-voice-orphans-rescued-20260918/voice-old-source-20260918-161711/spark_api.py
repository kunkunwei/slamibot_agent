#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
讯飞星火API集成模块
Xunfei Spark API Integration Module

包含：
- ASR: 语音听写（语音转文字）
- TTS: 在线语音合成（文字转语音）
- Spark: 星火大模型对话
"""

import os
import json
import time
import base64
import hashlib
import hmac
import struct
import threading
from datetime import datetime
from urllib.parse import urlencode, urlparse
from typing import Callable, Optional, Dict, Any

import websocket

try:
    import yaml
except ImportError:
    yaml = None

try:
    from ament_index_python.packages import get_package_share_directory
    _ROS_AVAILABLE = True
except ImportError:
    _ROS_AVAILABLE = False


# ==================== 配置加载 ====================
def load_config() -> Dict[str, Any]:
    """
    从 YAML 配置文件加载配置
    Load configuration from YAML config file

    优先级 / Priority:
    1. 环境变量 / Environment variables
    2. YAML 配置文件 / YAML config file
    """
    config = {
        'appid': '',
        'api_key': '',
        'api_secret': '',
        'spark_model': 'lite',
        'tts_voice': 'xiaoyan',
        'tts_speed': 50,
        'tts_volume': 50,
        'tts_pitch': 50,
    }

    # 尝试从 YAML 文件加载
    config_paths = []

    # ROS2 包路径
    if _ROS_AVAILABLE:
        try:
            share_dir = get_package_share_directory('xf_mic')
            config_paths.append(os.path.join(share_dir, 'config', 'xf_config.yaml'))
        except Exception:
            pass

    # 相对路径（开发时使用）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 自包含独立目录：与 spark_api.py 同目录的 xf_config.yaml（优先）
    config_paths.append(os.path.join(script_dir, 'xf_config.yaml'))
    # ROS2 包内开发路径：scripts/../config/xf_config.yaml
    config_paths.append(os.path.join(script_dir, '..', 'config', 'xf_config.yaml'))
    # 当前工作目录
    config_paths.append(os.path.join(os.getcwd(), 'xf_config.yaml'))

    # 尝试加载 YAML 配置
    if yaml is not None:
        for config_path in config_paths:
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        yaml_config = yaml.safe_load(f)
                        if yaml_config:
                            config.update({k: v for k, v in yaml_config.items() if v})
                    break
                except Exception as e:
                    print(f"警告: 加载配置文件失败 {config_path}: {e}")

    # 环境变量覆盖（优先级最高）
    env_mapping = {
        'SPARK_APP_ID': 'appid',
        'SPARK_API_KEY': 'api_key',
        'SPARK_API_SECRET': 'api_secret',
    }
    for env_key, config_key in env_mapping.items():
        env_value = os.environ.get(env_key, '')
        if env_value:
            config[config_key] = env_value

    return config


# 加载配置
_CONFIG = load_config()

# 统一凭证（ASR/TTS/Spark 使用相同的凭证）
APP_ID = _CONFIG.get('appid', '')
API_KEY = _CONFIG.get('api_key', '')
API_SECRET = _CONFIG.get('api_secret', '')

# 默认配置
DEFAULT_SPARK_MODEL = _CONFIG.get('spark_model', 'v3.5')
DEFAULT_TTS_VOICE = _CONFIG.get('tts_voice', 'xiaoyan')
DEFAULT_TTS_SPEED = _CONFIG.get('tts_speed', 50)
DEFAULT_TTS_VOLUME = _CONFIG.get('tts_volume', 50)
DEFAULT_TTS_PITCH = _CONFIG.get('tts_pitch', 50)
DEFAULT_SILENCE_TIMEOUT = _CONFIG.get('silence_timeout', 1.5)
DEFAULT_MAX_RECORD_TIME = _CONFIG.get('max_record_time', 30.0)
DEFAULT_COMMAND_RECOGNITION_MODE = _CONFIG.get('command_recognition_mode', 'offline')
DEFAULT_TTS_MODE = _CONFIG.get('tts_mode', 'offline')


def get_config() -> Dict[str, Any]:
    """
    获取当前配置（供其他模块使用）
    Get current configuration (for use by other modules)
    """
    return _CONFIG.copy()


def create_auth_url(host: str, path: str, api_key: str, api_secret: str) -> str:
    """
    创建带鉴权的WebSocket URL
    Create WebSocket URL with authentication

    讯飞API使用HMAC-SHA256签名进行鉴权
    Xunfei API uses HMAC-SHA256 signature for authentication
    """
    # 生成RFC1123格式的时间戳
    now = datetime.utcnow()
    date = now.strftime('%a, %d %b %Y %H:%M:%S GMT')

    # 构建签名原文
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"

    # HMAC-SHA256签名
    signature_sha = hmac.new(
        api_secret.encode('utf-8'),
        signature_origin.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    signature = base64.b64encode(signature_sha).decode('utf-8')

    # 构建authorization
    authorization_origin = (
        f'api_key="{api_key}", '
        f'algorithm="hmac-sha256", '
        f'headers="host date request-line", '
        f'signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')

    # 构建最终URL
    params = {
        'authorization': authorization,
        'date': date,
        'host': host
    }
    url = f"wss://{host}{path}?{urlencode(params)}"
    return url


# ==================== ASR 语音听写 ====================
class XfASR:
    """
    讯飞语音听写（实时语音转文字）
    Xunfei Speech Dictation (Real-time Speech to Text)

    API文档: https://www.xfyun.cn/doc/asr/voicedictation/API.html
    """

    HOST = "iat-api.xfyun.cn"
    PATH = "/v2/iat"

    def __init__(self, app_id: str = None, api_key: str = None, api_secret: str = None):
        self.app_id = app_id or APP_ID
        self.api_key = api_key or API_KEY
        self.api_secret = api_secret or API_SECRET

        self.result_text = ""
        self.is_finished = False
        self.error_msg = None
        self._ws = None

    def _create_params(self, audio_data: bytes, status: int) -> dict:
        """
        创建请求参数
        Create request parameters

        status: 0=第一帧, 1=中间帧, 2=最后一帧
        status: 0=first frame, 1=middle frame, 2=last frame
        """
        params = {
            "common": {
                "app_id": self.app_id
            },
            "business": {
                "language": "zh_cn",      # 中文
                "domain": "iat",          # 日常用语
                "accent": "mandarin",     # 普通话
                "vad_eos": 3000,          # 静音检测时长(ms)
                # "dwa": "wpgs",          # 动态修正 (已关闭，防止未处理的pgs逻辑导致结果重复)
                "ptt": 1,                 # 标点
                "nunum": 1,               # 数字格式
            },
            "data": {
                "status": status,
                "format": "audio/L16;rate=16000",
                "encoding": "raw",
                "audio": base64.b64encode(audio_data).decode('utf-8')
            }
        }
        return params

    def _on_message(self, ws, message):
        """处理服务器返回的消息"""
        try:
            result = json.loads(message)
            code = result.get("code", -1)

            if code != 0:
                self.error_msg = f"ASR错误: code={code}, msg={result.get('message', 'unknown')}"
                self.is_finished = True
                return

            data = result.get("data", {})
            status = data.get("status", 0)

            # 解析识别结果
            ws_result = data.get("result", {})
            if ws_result:
                ws_list = ws_result.get("ws", [])
                for ws_item in ws_list:
                    cw_list = ws_item.get("cw", [])
                    for cw in cw_list:
                        self.result_text += cw.get("w", "")

            # status=2 表示识别结束
            if status == 2:
                self.is_finished = True

        except Exception as e:
            self.error_msg = f"解析ASR响应失败: {e}"
            self.is_finished = True

    def _on_error(self, ws, error):
        """处理错误"""
        self.error_msg = f"ASR WebSocket错误: {error}"
        self.is_finished = True

    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭"""
        self.is_finished = True

    def recognize(self, audio_data: bytes, frame_size: int = 1280) -> str:
        """
        识别音频数据
        Recognize audio data

        Args:
            audio_data: PCM音频数据 (16kHz, 16bit, 单声道)
            frame_size: 每帧大小（字节），默认1280（40ms）

        Returns:
            识别出的文字
        """
        self.result_text = ""
        self.is_finished = False
        self.error_msg = None

        # 创建鉴权URL
        url = create_auth_url(self.HOST, self.PATH, self.api_key, self.api_secret)

        # 创建WebSocket连接
        ws = websocket.WebSocketApp(
            url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )

        def run_ws():
            ws.run_forever()

        # 在后台线程运行WebSocket
        ws_thread = threading.Thread(target=run_ws)
        ws_thread.daemon = True
        ws_thread.start()

        # 等待连接建立
        time.sleep(0.5)

        # 分帧发送音频
        total_len = len(audio_data)
        offset = 0
        frame_count = 0

        while offset < total_len and not self.is_finished:
            end = min(offset + frame_size, total_len)
            chunk = audio_data[offset:end]

            # 确定帧状态
            if offset == 0:
                status = 0  # 第一帧
            elif end >= total_len:
                status = 2  # 最后一帧
            else:
                status = 1  # 中间帧

            try:
                params = self._create_params(chunk, status)
                ws.send(json.dumps(params))
            except Exception as e:
                self.error_msg = f"发送音频数据失败: {e}"
                break

            offset = end
            frame_count += 1

            # 控制发送速率（模拟实时）
            time.sleep(0.04)

        # 等待识别完成
        timeout = 10
        start_time = time.time()
        while not self.is_finished and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        ws.close()

        if self.error_msg:
            raise Exception(self.error_msg)

        return self.result_text


# ==================== TTS 语音合成 ====================
class XfTTS:
    """
    讯飞在线语音合成（文字转语音）
    Xunfei Online Text-to-Speech

    API文档: https://www.xfyun.cn/doc/tts/online_tts/API.html
    """

    HOST = "tts-api.xfyun.cn"
    PATH = "/v2/tts"

    def __init__(self, app_id: str = None, api_key: str = None, api_secret: str = None):
        self.app_id = app_id or APP_ID
        self.api_key = api_key or API_KEY
        self.api_secret = api_secret or API_SECRET

        self.audio_data = b""
        self.is_finished = False
        self.error_msg = None
        
        # 流式回调和中断支持
        self.on_audio_callback: Optional[Callable[[bytes], None]] = None
        self.stop_flag = False
        self._ws = None
        
        # 播放进程和音频队列（用于即时打断）
        self._aplay_process = None
        self._audio_queue = None

    def _create_params(self, text: str, voice: str = "xiaoyan", speed: int = 50,
                       volume: int = 50, pitch: int = 50) -> dict:
        """
        创建请求参数
        Create request parameters

        Args:
            text: 要合成的文本
            voice: 发音人（xiaoyan, aisjiuxu, aisxping, aisjinger等）
            speed: 语速 (0-100)
            volume: 音量 (0-100)
            pitch: 音高 (0-100)
        """
        params = {
            "common": {
                "app_id": self.app_id
            },
            "business": {
                "aue": "raw",           # 音频编码：raw=PCM
                "auf": "audio/L16;rate=16000",  # 音频格式
                "vcn": voice,           # 发音人
                "speed": speed,         # 语速
                "volume": volume,       # 音量
                "pitch": pitch,         # 音高
                "tte": "UTF8"           # 文本编码
            },
            "data": {
                "status": 2,            # 一次性发送
                "text": base64.b64encode(text.encode('utf-8')).decode('utf-8')
            }
        }
        return params

    def _on_message(self, ws, message):
        """处理服务器返回的消息"""
        try:
            result = json.loads(message)
            code = result.get("code", -1)

            if code != 0:
                self.error_msg = f"TTS错误: code={code}, msg={result.get('message', 'unknown')}"
                self.is_finished = True
                return

            data = result.get("data", {})
            audio = data.get("audio", "")
            status = data.get("status", 0)

            if audio:
                audio_chunk = base64.b64decode(audio)
                self.audio_data += audio_chunk
                
                # 流式回调：立即发送音频片段
                if self.on_audio_callback:
                    self.on_audio_callback(audio_chunk)

            # status=2 表示合成结束
            if status == 2:
                self.is_finished = True

        except Exception as e:
            self.error_msg = f"解析TTS响应失败: {e}"
            self.is_finished = True

    def _on_error(self, ws, error):
        """处理错误"""
        self.error_msg = f"TTS WebSocket错误: {error}"
        self.is_finished = True

    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭"""
        self.is_finished = True

    def play_text(self, text: str, device_str: str, voice: str = None, speed: int = None,
                 volume: int = None, pitch: int = None):
        """
        直接播放合成语音
        Directly play synthesized speech

        Args:
            text: 要播放的文本
            device_str: 播放设备字符串 (e.g. "plughw:2,0")
            voice: 发音人
        """
        import subprocess
        import queue
        import threading
        
        # 重置状态
        self.stop_flag = False
        self._audio_queue = queue.Queue()
        
        # 1. 启动播放进程
        # aplay parameters:
        # -D: device
        # -q: quiet
        # -t raw: raw data
        # -f S16_LE: format
        # -r 16000: rate
        # -c 1: channels
        cmd = ['aplay', '-D', device_str, '-q', '-t', 'raw', '-f', 'S16_LE', '-r', '16000', '-c', '1']
        self._aplay_process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        def writer_task():
            while True:
                # 1. 检查停止标志
                if self.stop_flag:
                    break
                try:
                    chunk = self._audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if chunk is None: # 结束信号
                    break
                # 2. 再次检查停止标志
                if self.stop_flag:
                    break
                # 如果进程还活着，则写入；否则退出
                if self._aplay_process and self._aplay_process.poll() is None:
                    try:
                        self._aplay_process.stdin.write(chunk)
                        self._aplay_process.stdin.flush()
                    except Exception:
                        pass
                else:
                    break

        writer_thread = threading.Thread(target=writer_task)
        writer_thread.start()
        
        def on_audio_chunk(chunk: bytes):
            # 将数据放入队列，不阻塞回调
            if not self.stop_flag and self._audio_queue:
                self._audio_queue.put(chunk)
        try:
            self.synthesize_stream(text, on_audio=on_audio_chunk, voice=voice, 
                                 speed=speed, volume=volume, pitch=pitch)
        finally:
            # 合成结束（或被打断）
            
            if self.stop_flag:
                
                if self._aplay_process:
                    try:
                        self._aplay_process.kill()
                        self._aplay_process.wait(timeout=0.1)
                    except:
                        pass
                try:
                    while not self._audio_queue.empty():
                        self._audio_queue.get_nowait()
                except:
                    pass
                
                self._audio_queue.put(None) 
                
                writer_thread.join(timeout=1.0)
            else:
                self._audio_queue.put(None) 
                
                writer_thread.join() 
                
                if self._aplay_process:
                    try:
                        self._aplay_process.stdin.close()
                        # 等待aplay播放完缓冲区里的最后一点数据
                        self._aplay_process.wait() 
                    except Exception:
                        try:
                            self._aplay_process.kill()
                        except:
                            pass
            
            # 清理类成员变量
            self._aplay_process = None
            self._audio_queue = None

    def stop(self):
        """
        停止当前TTS合成（用于打断）
        Stop current TTS synthesis (for interruption)
        """
        self.stop_flag = True
        
        # 1. 立即杀死播放进程（这是停止声音最快的方法）
        if self._aplay_process:
            try:
                self._aplay_process.kill()
            except:
                pass
        
        # 2. 清空音频队列（防止消费者继续写入）
        if self._audio_queue:
            try:
                while not self._audio_queue.empty():
                    self._audio_queue.get_nowait()
            except:
                pass
        
        # 3. 关闭 WebSocket
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def synthesize_stream(self, text: str, on_audio: Callable[[bytes], None],
                          voice: str = None, speed: int = None,
                          volume: int = None, pitch: int = None) -> bool:
        """
        流式合成语音（边合成边回调）
        Streaming speech synthesis (callback on each audio chunk)

        Args:
            text: 要合成的文本（最大1000字）
            on_audio: 音频片段回调函数，每收到一段音频立即调用
            voice: 发音人（默认从配置文件读取）
            speed: 语速 (0-100)
            volume: 音量 (0-100)
            pitch: 音高 (0-100)

        Returns:
            True=正常完成, False=被中断
        """
        # 使用默认配置
        voice = voice or DEFAULT_TTS_VOICE
        speed = speed if speed is not None else DEFAULT_TTS_SPEED
        volume = volume if volume is not None else DEFAULT_TTS_VOLUME
        pitch = pitch if pitch is not None else DEFAULT_TTS_PITCH

        self.audio_data = b""
        self.is_finished = False
        self.error_msg = None
        self.stop_flag = False
        self.on_audio_callback = on_audio

        # 文本长度限制
        if len(text) > 1000:
            text = text[:1000]

        # 创建鉴权URL
        url = create_auth_url(self.HOST, self.PATH, self.api_key, self.api_secret)

        # 创建WebSocket连接
        self._ws = websocket.WebSocketApp(
            url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )

        def on_open(ws):
            if not self.stop_flag:
                params = self._create_params(text, voice, speed, volume, pitch)
                ws.send(json.dumps(params))

        self._ws.on_open = on_open

        def run_ws():
            self._ws.run_forever()

        # 在后台线程运行WebSocket
        ws_thread = threading.Thread(target=run_ws)
        ws_thread.daemon = True
        ws_thread.start()

        # 等待合成完成或被中断
        timeout = 30
        start_time = time.time()
        while not self.is_finished and not self.stop_flag and (time.time() - start_time) < timeout:
            time.sleep(0.05)  # 更短的检查间隔

        self._ws.close()
        self.on_audio_callback = None

        if self.stop_flag:
            return False  # 被中断

        if self.error_msg:
            raise Exception(self.error_msg)

        return True  # 正常完成

    def synthesize(self, text: str, voice: str = None, speed: int = None,
                   volume: int = None, pitch: int = None) -> bytes:
        """
        合成语音（阻塞模式，用于兼容）
        Synthesize speech (blocking mode, for backward compatibility)

        Args:
            text: 要合成的文本（最大1000字）
            voice: 发音人（默认从配置文件读取）
            speed: 语速 (0-100)
            volume: 音量 (0-100)
            pitch: 音高 (0-100)

        Returns:
            PCM音频数据 (16kHz, 16bit, 单声道)
        """
        # 使用流式合成，但不使用回调
        self.synthesize_stream(text, lambda chunk: None, voice, speed, volume, pitch)
        return self.audio_data


# ==================== Spark 大模型 ====================
class XfSpark:
    """
    讯飞星火大模型
    Xunfei Spark Large Language Model

    API文档: https://www.xfyun.cn/doc/spark/Web.html
    """
    VERSIONS = {
        # Spark Lite - 轻量版
        "lite":       {"host": "spark-api.xf-yun.com", "path": "/v1.1/chat", "domain": "lite"},
        # Spark Pro - 专业版
        "pro":        {"host": "spark-api.xf-yun.com", "path": "/v3.1/chat", "domain": "generalv3"},
        # Spark Pro-128K - 专业版长文本
        "pro-128k":   {"host": "spark-api.xf-yun.com", "path": "/chat/pro-128k", "domain": "pro-128k"},
        # Spark Max - 旗舰版
        "max":        {"host": "spark-api.xf-yun.com", "path": "/v3.5/chat", "domain": "generalv3.5"},
        # Spark Max-32K - 旗舰版长文本
        "max-32k":    {"host": "spark-api.xf-yun.com", "path": "/chat/max-32k", "domain": "max-32k"},
        # Spark 4.0 Ultra - 顶配版
        "ultra":      {"host": "spark-api.xf-yun.com", "path": "/v4.0/chat", "domain": "4.0Ultra"},
    }

    def __init__(self, app_id: str = None, api_key: str = None, api_secret: str = None,
                 model: str = None):
        self.app_id = app_id or APP_ID
        self.api_key = api_key or API_KEY
        self.api_secret = api_secret or API_SECRET

        # 使用传入模型或配置文件中的默认模型
        model = model or DEFAULT_SPARK_MODEL
        if model not in self.VERSIONS:
            raise ValueError(f"不支持的模型: {model}，支持: {list(self.VERSIONS.keys())}")

        self.model = model
        self.host = self.VERSIONS[model]["host"]
        self.path = self.VERSIONS[model]["path"]
        self.domain = self.VERSIONS[model]["domain"]

        self.response_text = ""
        self.is_finished = False
        self.error_msg = None
        self.on_token_callback: Optional[Callable[[str], None]] = None
        
        # 中断支持
        self.stop_flag = False
        self._ws = None

    def _create_params(self, messages: list, max_tokens: int = 2048,
                       temperature: float = 0.5) -> dict:
        """
        创建请求参数
        Create request parameters

        Args:
            messages: 对话历史 [{"role": "user/assistant", "content": "..."}]
            max_tokens: 最大生成token数
            temperature: 温度参数 (0-1)
        """
        params = {
            "header": {
                "app_id": self.app_id,
                "uid": "user_001"
            },
            "parameter": {
                "chat": {
                    "domain": self.domain,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            },
            "payload": {
                "message": {
                    "text": messages
                }
            }
        }
        return params

    def _on_message(self, ws, message):
        """处理服务器返回的消息"""
        try:
            result = json.loads(message)
            header = result.get("header", {})
            code = header.get("code", -1)

            if code != 0:
                self.error_msg = f"Spark错误: code={code}, msg={header.get('message', 'unknown')}"
                self.is_finished = True
                return

            payload = result.get("payload", {})
            choices = payload.get("choices", {})
            text_list = choices.get("text", [])
            status = choices.get("status", 0)

            for text_item in text_list:
                content = text_item.get("content", "")
                self.response_text += content

                # 流式回调
                if self.on_token_callback and content:
                    self.on_token_callback(content)

            # status=2 表示回复结束
            if status == 2:
                self.is_finished = True

        except Exception as e:
            self.error_msg = f"解析Spark响应失败: {e}"
            self.is_finished = True

    def _on_error(self, ws, error):
        """处理错误"""
        self.error_msg = f"Spark WebSocket错误: {error}"
        self.is_finished = True

    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭"""
        self.is_finished = True

    def chat(self, user_input: str, history: list = None, system_prompt: str = None,
             max_tokens: int = 2048, temperature: float = 0.5,
             on_token: Callable[[str], None] = None) -> str:
        """
        与大模型对话
        Chat with the large language model

        Args:
            user_input: 用户输入
            history: 对话历史 [{"role": "user/assistant", "content": "..."}]
            system_prompt: 系统提示词
            max_tokens: 最大生成token数
            temperature: 温度参数 (0-1)
            on_token: 流式输出回调函数

        Returns:
            模型回复
        """
        self.response_text = ""
        self.is_finished = False
        self.error_msg = None
        self.stop_flag = False
        self.on_token_callback = on_token

        # 构建消息列表
        messages = []

        # 添加系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加历史对话
        if history:
            messages.extend(history)

        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})

        # 创建鉴权URL
        url = create_auth_url(self.host, self.path, self.api_key, self.api_secret)

        # 创建WebSocket连接
        self._ws = websocket.WebSocketApp(
            url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )

        def on_open(ws):
            if not self.stop_flag:
                params = self._create_params(messages, max_tokens, temperature)
                ws.send(json.dumps(params))

        self._ws.on_open = on_open

        def run_ws():
            self._ws.run_forever()

        # 在后台线程运行WebSocket
        ws_thread = threading.Thread(target=run_ws)
        ws_thread.daemon = True
        ws_thread.start()

        # 等待回复完成或被中断
        timeout = 60
        start_time = time.time()
        while not self.is_finished and not self.stop_flag and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        self._ws.close()
        self._ws = None
        self.on_token_callback = None
        
        if self.stop_flag:
            return self.response_text  # 被中断，返回已生成部分

        if self.error_msg:
            raise Exception(self.error_msg)

        return self.response_text
    
    def stop(self):
        """
        停止当前LLM生成（用于打断）
        Stop current LLM generation (for interruption)
        """
        self.stop_flag = True
        self.on_token_callback = None  # 停止回调
        if self._ws:
            try:
                self._ws.close()
            except:
                pass


# ==================== 便捷函数 ====================
def speech_to_text(audio_data: bytes) -> str:
    """
    语音转文字（便捷函数）
    Speech to text (convenience function)

    Args:
        audio_data: PCM音频数据 (16kHz, 16bit, 单声道)

    Returns:
        识别出的文字
    """
    asr = XfASR()
    return asr.recognize(audio_data)


def text_to_speech(text: str, voice: str = None) -> bytes:
    """
    文字转语音（便捷函数）
    Text to speech (convenience function)

    Args:
        text: 要合成的文本
        voice: 发音人（默认从配置文件读取）

    Returns:
        PCM音频数据 (16kHz, 16bit, 单声道)
    """
    tts = XfTTS()
    return tts.synthesize(text, voice)


def chat_with_spark(user_input: str, history: list = None,
                    system_prompt: str = None, model: str = None,
                    on_token: Callable[[str], None] = None) -> str:
    """
    与星火大模型对话（便捷函数）
    Chat with Spark LLM (convenience function)

    Args:
        user_input: 用户输入
        history: 对话历史
        system_prompt: 系统提示词
        model: 模型名称（默认从配置文件读取）
        on_token: 流式输出回调

    Returns:
        模型回复
    """
    spark = XfSpark(model=model)
    return spark.chat(user_input, history, system_prompt, on_token=on_token)


# ==================== 测试代码 ====================
if __name__ == "__main__":
    print("讯飞星火API集成模块")
    print("=" * 50)

    # 检查配置
    if not APP_ID or not API_KEY or not API_SECRET:
        print("警告: 未配置API凭证！")
        print("请编辑配置文件 config/xf_config.yaml 或设置环境变量：")
        print("  SPARK_APP_ID")
        print("  SPARK_API_KEY")
        print("  SPARK_API_SECRET")
    else:
        print(f"APP_ID: {APP_ID[:4]}****")
        print(f"Spark模型: {DEFAULT_SPARK_MODEL}")
        print(f"TTS发音人: {DEFAULT_TTS_VOICE}")
        print("API凭证已配置")

        # 测试Spark对话
        print("\n测试Spark大模型对话...")
        try:
            response = chat_with_spark("你好，请简单介绍一下你自己")
            print(f"Spark回复: {response}")
        except Exception as e:
            print(f"Spark测试失败: {e}")
