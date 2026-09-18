#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Launch 进程管理器。

负责启动/停止/查询 Scout Mini 的 ROS launch 进程:
- lidar_to_scan.launch (基础感知层: 底盘 + TF + /scan)
- gmapping.launch       (建图模式)
- my_nav_launch.launch  (导航模式: map_server + AMCL + move_base)

进程通过 subprocess.Popen 启动,使用进程组管理,停止时连带子进程一起清理。
工作区路径可通过环境变量 SCOUT_NAV_WS 指定,默认 /home/jetson/Scout_mini_navigation。
"""
import os
import signal
import subprocess
import threading
import time

try:
    import rospkg
except ImportError:  # pragma: no cover - only absent outside ROS
    rospkg = None

try:
    from . import db as _db
except ImportError:
    import db as _db


# 工作区仅用于 source setup.bash；包内资源由 rospack 解析。
WORKSPACE = os.environ.get("SCOUT_NAV_WS", "/home/jetson/Scout_mini_navigation")
_ROSPACK = rospkg.RosPack() if rospkg is not None else None


def _package_path(package):
    """Resolve install/source package paths without requiring src at runtime."""
    configured = os.environ.get("%s_PACKAGE_SHARE" % package.upper())
    if configured:
        return configured
    if _ROSPACK is not None:
        return _ROSPACK.get_path(package)
    # Non-ROS local static-analysis fallback only.
    return os.path.join(WORKSPACE, "src", package)


def _resource_path(package, *parts):
    return os.path.join(_package_path(package), *parts)


_LAUNCH_ROOT = _resource_path("my_nav", "launch")
_MAPPING_ROOT = _resource_path("my_nav", "mapping_launch")

# 进程句柄
_base_process = None
_mapping_process = None
_navigation_process = None

# 运行状态
_current_mode = "idle"      # idle / mapping / navigation
_mode_switching = False     # 切换中锁,防止并发切换
_lock = threading.Lock()

# PCD 发布进程(pcd_map_publisher.py → /global_cloud_navigation)
_pcd_process = None
_pcd_last_file = None       # 上次启动的文件路径,崩溃重启用
_pcd_last_restart = 0.0     # 上次重启时间戳,防止连续崩溃时死循环

# 启动后等待检查的秒数
_LAUNCH_CHECK_WAIT = 3.0

# 模式切换时,基础层与上层 launch 之间的额外稳定等待(秒)
_INTER_LAUNCH_DELAY = 3.0

# 导航启动前 ROS 时间轻量预检超时(秒)。只 fail-fast，不自动重启任何节点。
try:
    _ROS_TIME_CHECK_TIMEOUT = max(
        0.5, float(os.environ.get("ROS_TIME_CHECK_TIMEOUT_SEC", "5"))
    )
except ValueError:
    _ROS_TIME_CHECK_TIMEOUT = 5.0

# Writable/generated PCD data is configured explicitly or resolved from installed maps.
_FASTLIO_PCD_DIR = os.environ.get(
    "FASTLIO_PCD_DIR", os.path.join(os.environ.get("SCOUT_NAV_DATA_DIR", "/var/lib/slamibot"), "fastlio", "PCD")
)


def _is_running(process):
    """检查进程是否仍在运行。"""
    return process is not None and process.poll() is None


def _get_setup_cmd():
    """返回 source setup.bash 的命令前缀（优先 install，兼容 devel）。"""
    install_setup = f"{WORKSPACE}/install/setup.bash"
    if os.path.isfile(install_setup):
        return f"source {install_setup}"
    return f"source {WORKSPACE}/devel/setup.bash"


def _check_ros_time_ready(timeout_sec=None):
    """检查导航所需 ROS 模拟时间；不修改参数、不重启任何进程。"""
    timeout_sec = timeout_sec or _ROS_TIME_CHECK_TIMEOUT
    try:
        param_result = subprocess.run(
            ["rosparam", "get", "/use_sim_time"],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "ROS时间未就绪: 读取 /use_sim_time 超时"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"ROS时间未就绪: 无法读取 /use_sim_time ({exc})"

    if param_result.returncode != 0:
        detail = (param_result.stderr or param_result.stdout).strip()
        return False, f"ROS时间未就绪: 无法读取 /use_sim_time ({detail or 'ROS Master不可用'})"
    if param_result.stdout.strip().lower() != "true":
        return False, "ROS时间未就绪: /use_sim_time 不是 true"

    try:
        clock_result = subprocess.run(
            ["rostopic", "echo", "-n", "1", "/clock"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"ROS时间未就绪: {timeout_sec:g}s 内未收到 /clock"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"ROS时间未就绪: 无法读取 /clock ({exc})"

    if clock_result.returncode != 0:
        detail = (clock_result.stderr or "").strip()
        return False, f"ROS时间未就绪: /clock 读取失败 ({detail or '未知错误'})"
    return True, "ROS时间已就绪"


def _start_launch(launch_path, args=None, wait=_LAUNCH_CHECK_WAIT):
    """启动一个 roslaunch 进程。

    Args:
        launch_path: launch 文件绝对路径
        args: 传递给 roslaunch 的参数列表,如 ["map_file:=/xxx.yaml"]
        wait: 启动后等待几秒检查进程是否立即退出

    Returns:
        (process, err_msg): process 为 None 表示启动失败
    """
    if not os.path.exists(WORKSPACE):
        return None, f"工作空间不存在: {WORKSPACE},请检查 SCOUT_NAV_WS 环境变量"
    if not os.path.exists(launch_path):
        return None, f"launch 文件不存在: {launch_path}"

    package = "my_nav"
    launch_name = os.path.basename(launch_path)
    # 保留 .launch 后缀: roslaunch 要求 <package> <file.launch> 形式
    if not launch_name.endswith(".launch"):
        return None, f"launch 文件名必须以 .launch 结尾: {launch_name}"

    cmd = f"{_get_setup_cmd()} && roslaunch {package} {launch_name}"
    if args:
        cmd += " " + " ".join(args)

    try:
        process = subprocess.Popen(
            cmd,
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # 创建新进程组,便于整体停止
        )
    except Exception as e:
        return None, f"启动进程失败: {str(e)}"

    # 等待并检查进程是否立即退出
    if wait > 0:
        time.sleep(wait)
        if process.poll() is not None:
            return None, f"launch 进程启动后立即退出,返回码: {process.poll()},请检查前置条件(/clock、雷达话题、CAN 等)"

    return process, None


def _stop_launch(process, term_timeout=5):
    """停止一个 launch 进程及其子进程。

    Args:
        process: subprocess.Popen 句柄
        term_timeout: SIGTERM 后等待进程退出的秒数(FAST_LIO 写 PCD 需要更久)

    Returns:
        bool: 是否成功停止
    """
    if process is None or process.poll() is not None:
        return True
    try:
        # 先 SIGTERM 整个进程组
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        try:
            process.wait(timeout=term_timeout)
        except subprocess.TimeoutExpired:
            # 超时后 SIGKILL
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.wait(timeout=2)
        return True
    except ProcessLookupError:
        return True
    except Exception:
        return False


def _get_active_map_yaml():
    """从数据库获取当前激活地图的 yaml 文件路径。"""
    try:
        with _db.get_conn() as conn:
            row = conn.execute(
                "SELECT yamlFilePath FROM Map WHERE isActive = 1 LIMIT 1"
            ).fetchone()
            if row and row["yamlFilePath"]:
                return row["yamlFilePath"]
            return None
    except Exception:
        return None


def _get_active_map_pcd():
    """从数据库获取当前激活地图的 pcd 文件路径。"""
    try:
        with _db.get_conn() as conn:
            row = conn.execute(
                "SELECT pcdFilePath FROM Map WHERE isActive = 1 LIMIT 1"
            ).fetchone()
            if row and row["pcdFilePath"]:
                return row["pcdFilePath"]
            return None
    except Exception:
        return None


# ============================================================
# PCD 地图发布(pcd_map_publisher.py → /global_cloud_navigation)
# ============================================================

def start_pcd(pcd_file=None):
    """启动 pcd_map_publisher.py 节点,发布 /global_cloud_navigation。

    Args:
        pcd_file: pcd 文件绝对路径。为 None 时自动从激活地图的 pcdFilePath 读取。

    Returns:
        (success, msg)
    """
    global _pcd_process, _pcd_last_file
    if pcd_file is None:
        pcd_file = _get_active_map_pcd()
    if not pcd_file:
        return False, "激活地图未配置 pcdFilePath,跳过 PCD 发布"
    if not os.path.exists(pcd_file):
        return False, f"PCD 文件不存在: {pcd_file}"
    display_pcd = os.path.splitext(pcd_file)[0] + "_display.pcd"
    if not os.path.exists(display_pcd):
        return False, (
            f"降采样点云不存在: {display_pcd},"
            "请先调用 FastAPI /api/map/downsample 接口"
        )

    with _lock:
        # 新地图显示文件确认可用后再停旧发布器，避免切换失败导致点云立即消失。
        _stop_launch(_pcd_process)
        _pcd_process = None

        # nice 降低优先级,避免加载大 PCD 时抢占导航栈 CPU
        cmd = (
            f"{_get_setup_cmd()} && "
            f"nice -n 10 rosrun nav_api pcd_map_publisher.py "
            f"_pcd_file:={pcd_file} _frame_id:=map"
        )
        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                executable="/bin/bash",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as e:
            return False, f"启动 pcd_map_publisher 失败: {str(e)}"

        _pcd_process = process
        _pcd_last_file = pcd_file
        return True, f"pcd_map_publisher 已启动: {pcd_file}"


def stop_pcd():
    """停止 pcd_map_publisher.py 节点。"""
    global _pcd_process
    with _lock:
        if _stop_launch(_pcd_process):
            _pcd_process = None
            return True, "pcd_map_publisher 已停止"
        return False, "停止 pcd_map_publisher 失败"


# ============================================================
# 基础感知层
# ============================================================

def start_base():
    """启动 lidar_to_scan.launch (基础感知层)。"""
    global _base_process
    with _lock:
        if _is_running(_base_process):
            return True, "基础感知层已在运行"
        launch_path = os.path.join(_LAUNCH_ROOT, "lidar_to_scan.launch")
        process, err = _start_launch(launch_path)
        if process is None:
            return False, err
        _base_process = process
        return True, "基础感知层启动成功"


def stop_base():
    """停止 lidar_to_scan.launch,会先停止依赖它的建图和导航。"""
    global _base_process, _mapping_process, _navigation_process, _current_mode
    # 先停 PCD 发布器(它依赖导航层的 map frame)
    stop_pcd()
    with _lock:
        # 先停上层,再停基础层
        if _stop_launch(_mapping_process):
            _mapping_process = None
        if _stop_launch(_navigation_process):
            _navigation_process = None
        if _stop_launch(_base_process):
            _base_process = None
            _current_mode = "idle"
            return True, "基础感知层已停止"
        return False, "停止基础感知层失败"


# ============================================================
# 建图
# ============================================================

def start_mapping():
    """启动 fastlio_mapping.launch(FAST_LIO 3D 建图)。"""
    global _mapping_process
    with _lock:
        if not _is_running(_base_process):
            return False, "基础感知层未启动,请先启动 lidar_to_scan"
        if _is_running(_mapping_process):
            return True, "建图进程已在运行"
        # 确保 FAST_LIO 的 PCD 输出目录存在(退出时写 scans.pcd 需要)
        os.makedirs(_FASTLIO_PCD_DIR, exist_ok=True)
        launch_path = os.path.join(_MAPPING_ROOT, "fastlio_mapping.launch")
        process, err = _start_launch(launch_path)
        if process is None:
            return False, err
        _mapping_process = process
        return True, "建图进程启动成功"


def stop_mapping():
    """停止 fastlio_mapping.launch。

    FAST_LIO 收到 SIGTERM 后会把累积点云写到 PCD/scans.pcd 再退出,
    大地图(几千万点)写盘可能需要较久,所以给 30 秒超时。
    """
    global _mapping_process, _current_mode

    with _lock:
        if not _is_running(_mapping_process):
            _mapping_process = None
            if _current_mode == "mapping":
                _current_mode = "idle"
            return True, "建图进程未在运行"

        # 仅在确认活动建图进程即将停止时轮换旧文件,不删除唯一现存 scans.pcd。
        pcd_path = os.path.join(_FASTLIO_PCD_DIR, "scans.pcd")
        previous_pcd_path = os.path.join(_FASTLIO_PCD_DIR, "scans.previous.pcd")
        if os.path.exists(pcd_path):
            os.replace(pcd_path, previous_pcd_path)
        if not _stop_launch(_mapping_process, term_timeout=30):
            return False, "停止建图进程失败"
        _mapping_process = None
        if _current_mode == "mapping":
            _current_mode = "idle"

    return True, "建图进程已停止"


# ============================================================
# 导航
# ============================================================

def start_navigation(check_ros_time=True):
    """启动 my_nav_launch.launch (AMCL + move_base)。

    会自动从数据库读取当前激活地图的 yaml 路径并传入 launch。
    """
    global _navigation_process
    with _lock:
        if not _is_running(_base_process):
            return False, "基础感知层未启动,请先启动 lidar_to_scan"
        if _is_running(_navigation_process):
            return True, "导航进程已在运行"

        if check_ros_time:
            time_ok, time_msg = _check_ros_time_ready()
            if not time_ok:
                return False, time_msg

        yaml_path = _get_active_map_yaml()
        if not yaml_path:
            return False, "没有激活的地图,请先调用 /api/map/switch 切换地图"
        if not os.path.exists(yaml_path):
            return False, f"地图文件不存在: {yaml_path}"

        launch_path = os.path.join(_LAUNCH_ROOT, "my_nav_launch.launch")
        args = [f"map_file:={yaml_path}"]
        process, err = _start_launch(launch_path, args=args)
        if process is None:
            return False, err
        _navigation_process = process
        return True, "导航进程启动成功"


def stop_navigation():
    """停止 my_nav_launch.launch。"""
    global _navigation_process, _current_mode
    with _lock:
        if _stop_launch(_navigation_process):
            _navigation_process = None
            if _current_mode == "navigation":
                _current_mode = "idle"
            return True, "导航进程已停止"
        return False, "停止导航进程失败"


# ============================================================
# 模式切换
# ============================================================

def switch_to_mapping():
    """一键切换到建图模式。"""
    global _current_mode, _mode_switching
    with _lock:
        if _mode_switching:
            return False, "系统正在切换模式中,请稍后再试"
        if (
            _current_mode == "mapping"
            and _is_running(_mapping_process)
            and not _is_running(_navigation_process)
        ):
            return True, "当前已是建图模式"
        _mode_switching = True

    try:
        # 1. 停止导航(如有)
        ok, msg = stop_navigation()
        if not ok:
            return False, f"停止导航进程失败: {msg}"

        # 2. 切换到建图时停止 PCD 发布器(建图阶段不需要旧地图点云)
        stop_pcd()

        # 3. 启动基础感知层
        ok, msg = start_base()
        if not ok:
            return False, f"启动基础感知层失败: {msg}"

        # 等待基础层稳定(雷达/底盘 TF 就绪)后再启动建图
        time.sleep(_INTER_LAUNCH_DELAY)

        # 4. 启动建图
        ok, msg = start_mapping()
        if not ok:
            return False, f"启动建图失败: {msg}"

        with _lock:
            _current_mode = "mapping"
        return True, "已切换到建图模式"
    except Exception as e:
        return False, f"切换建图模式异常: {str(e)}"
    finally:
        with _lock:
            _mode_switching = False


def switch_to_navigation():
    """一键切换到导航模式。"""
    global _current_mode, _mode_switching
    with _lock:
        if _mode_switching:
            return False, "系统正在切换模式中,请稍后再试"
        if _current_mode == "navigation" and _is_running(_navigation_process):
            return True, "当前已是导航模式"
        _mode_switching = True

    try:
        # 在停止建图等破坏性操作前 fail-fast；本轮不做自动恢复。
        time_ok, time_msg = _check_ros_time_ready()
        if not time_ok:
            return False, time_msg

        # 1. 停止建图(如有)
        ok, msg = stop_mapping()
        if not ok:
            return False, f"停止建图进程失败: {msg}"

        # 2. 启动基础感知层
        ok, msg = start_base()
        if not ok:
            return False, f"启动基础感知层失败: {msg}"

        # 等待基础层稳定(雷达/底盘 TF 就绪)后再启动导航
        time.sleep(_INTER_LAUNCH_DELAY)

        # 3. 启动导航
        ok, msg = start_navigation(check_ros_time=False)
        if not ok:
            return False, f"启动导航失败: {msg}"

        # 4. 启动 PCD 发布器(从激活地图的 pcdFilePath 读取)
        pcd_ok, pcd_msg = start_pcd()
        if not pcd_ok:
            # PCD 不是必须的,只打日志不报错
            import logging
            logging.warning("PCD 发布器未启动: %s", pcd_msg)

        with _lock:
            _current_mode = "navigation"
        return True, "已切换到导航模式"
    except Exception as e:
        return False, f"切换导航模式异常: {str(e)}"
    finally:
        with _lock:
            _mode_switching = False


# ============================================================
# 状态查询
# ============================================================

def get_status():
    """获取当前 launch 进程状态。

    副作用: 检测到 PCD 发布器崩溃时自动尝试重启(带 5 秒间隔保护)。
    """
    global _pcd_last_restart
    with _lock:
        result = {
            "current_mode": _current_mode,
            "mode_switching": _mode_switching,
            "base_running": _is_running(_base_process),
            "mapping_running": _is_running(_mapping_process),
            "navigation_running": _is_running(_navigation_process),
            "pcd_running": _is_running(_pcd_process),
            "workspace": WORKSPACE,
        }
        pcd_dead = _pcd_process is not None and _pcd_process.poll() is not None

    # 锁外自动重启, 避免和 start_pcd() 内部的 _lock 死锁
    if pcd_dead and _pcd_last_file and (time.time() - _pcd_last_restart > 5):
        _pcd_last_restart = time.time()
        start_pcd(_pcd_last_file)

    return result


# ============================================================
# 默认模式持久化 + 幂等 ensure + 启动恢复
# ============================================================

_DEFAULT_MODE_KEY = "default_mode"
_DEFAULT_MODE_CHOICES = ("idle", "mapping", "navigation")


def get_default_mode():
    """读取持久化的默认启动模式;缺省/非法时返回 idle(保持现状,不自动切模式)。"""
    try:
        with _db.get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM SystemConfig WHERE key = ?",
                (_DEFAULT_MODE_KEY,),
            ).fetchone()
        if row and row["value"] in _DEFAULT_MODE_CHOICES:
            return row["value"]
    except Exception:
        pass
    return "idle"


def set_default_mode(mode):
    """持久化默认启动模式;非法值返回失败,不修改任何进程状态。"""
    if mode not in _DEFAULT_MODE_CHOICES:
        return False, f"非法默认模式: {mode} (可选: {'/'.join(_DEFAULT_MODE_CHOICES)})"
    try:
        with _db.get_conn() as conn:
            conn.execute(
                "INSERT INTO SystemConfig(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET "
                "value = excluded.value, updatedTime = datetime('now','localtime')",
                (_DEFAULT_MODE_KEY, mode),
            )
            conn.commit()
        return True, f"默认模式已设为 {mode}"
    except Exception as exc:
        return False, f"设置默认模式失败: {exc}"


def ensure_navigation():
    """幂等确保导航模式，但建图或切换期间严格 fail-closed。

    锁内只读取状态；建图模式、建图进程仍在运行或模式切换中均返回
    ``MAPPING_ACTIVE``，绝不调用 switch_to_navigation() 停止建图。
    """
    with _lock:
        mapping_active = (
            _current_mode == "mapping"
            or _is_running(_mapping_process)
            or _mode_switching
        )
        already = _current_mode == "navigation" and _is_running(_navigation_process)
    if mapping_active:
        return False, "MAPPING_ACTIVE"
    if already:
        return True, "当前已是导航模式"
    return switch_to_navigation()


def restore_default_mode():
    """启动恢复:按持久化的默认模式自动进入对应模式。

    非致命:任何失败都返回 (False, msg),由调用方打日志,不阻断 API 启动。
    容器刚启动时 ROS 时间(/clock)可能未就绪,switch 会 fail-fast,
    可依赖自检守护周期兜底(见 nav-healthcheck.sh)。
    """
    mode = get_default_mode()
    if mode == "navigation":
        return ensure_navigation()
    if mode == "mapping":
        return switch_to_mapping()
    return True, "默认模式为 idle,不做自动切换"
