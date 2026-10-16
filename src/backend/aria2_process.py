import ctypes
import subprocess
import time
import socket
import logging
import threading
from pathlib import Path
from typing import Optional

import psutil

from .config import config_manager
from .aria2_client import aria2_client

logger = logging.getLogger(__name__)


class Aria2StartError(Exception):
    """aria2c 启动失败"""


# ---------- Windows Job Object：OS 级进程回收保障 ----------
# 把 aria2c 绑定到 Job Object 并设置 KILL_ON_JOB_CLOSE：
# 本程序无论以何种方式退出（正常关闭 / Ctrl+C / 崩溃 / 被任务管理器结束），
# 内核都会自动终止 aria2c，彻底避免孤儿进程。

_JOB_OBJECT_EXTENDED_LIMIT_INFO = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_PROCESS_ALL_ACCESS = 0x1F0FFF


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
    )]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _attach_kill_on_close_job(process: subprocess.Popen) -> Optional[int]:
    """将子进程加入 Job Object，返回 job 句柄（故意保持打开，进程退出时由内核回收）"""
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.SetInformationJobObject.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
        kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None

        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
            job, _JOB_OBJECT_EXTENDED_LIMIT_INFO,
            ctypes.byref(info), ctypes.sizeof(info),
        ):
            kernel32.CloseHandle(job)
            return None

        handle = kernel32.OpenProcess(_PROCESS_ALL_ACCESS, False, process.pid)
        if not handle:
            kernel32.CloseHandle(job)
            return None
        try:
            kernel32.AssignProcessToJobObject(job, handle)
        finally:
            kernel32.CloseHandle(handle)
        logger.info("aria2c 已绑定 Job Object（宿主退出时自动回收）")
        return job
    except Exception as e:
        logger.warning("绑定 Job Object 失败（不影响正常使用）: %s", e)
        return None


class Aria2ProcessManager:
    """aria2c 进程管理器

    - 启动时端口被非 aria2 程序占用则直接报错（绝不强杀无关进程）
    - 关闭时优先走 RPC aria2.shutdown 优雅退出（触发会话保存），失败再强杀
    - 健康检查线程使用带 token 的 RPC 探活，进程意外退出时自动重启
    """

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        # 是否为复用的外部 aria2c（非本程序启动）
        self.external = False
        self._log_file = None
        self._job_handle: Optional[int] = None
        self._state_lock = threading.Lock()
        self._stop_health = threading.Event()
        self._health_thread: Optional[threading.Thread] = None
        self._restart_count = 0
        self._max_restart = 3

    # ---------- 启动 / 停止 ----------

    def start(self) -> None:
        """启动 aria2c（阻塞直到 RPC 可用），失败抛出 Aria2StartError"""
        with self._state_lock:
            if self.is_rpc_alive():
                logger.info("检测到可用的 aria2c RPC 服务，直接复用")
                self.external = self.process is None
                return

            aria2c_path = config_manager.get_aria2c_path()
            aria2c_file = Path(aria2c_path)
            if not aria2c_file.exists():
                raise Aria2StartError(f"找不到 aria2c: {aria2c_path}")

            if self._port_in_use():
                raise Aria2StartError(
                    f"端口 {config_manager.config.aria2_rpc_port} 已被其他程序占用，"
                    f"请修改配置文件中的 aria2_rpc_port"
                )

            config_manager.ensure_downloads_dir()
            cmd = self._build_command(aria2c_file)

            config_manager.log_dir.mkdir(parents=True, exist_ok=True)
            log_path = config_manager.log_dir / "aria2c.log"
            # 覆盖上次日志，句柄保存到实例上，stop() 时关闭
            self._log_file = open(log_path, "w", encoding="utf-8")

            logger.info("启动 aria2c: %s", mask_secret(cmd))
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.process = subprocess.Popen(
                [str(aria2c_file.absolute())] + cmd[1:],
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
            self._job_handle = _attach_kill_on_close_job(self.process)
            self.external = False

        # 等待 RPC 就绪（在锁外等待，避免阻塞 stop 等操作）
        if self._wait_for_rpc(timeout=20):
            logger.info("aria2c 启动成功，PID: %s", self.process.pid if self.process else "?")
            self._start_health_check()
        else:
            tail = self._read_log_tail()
            self.stop()
            raise Aria2StartError(f"aria2c RPC 启动超时。{tail}")

    def _build_command(self, aria2c_file: Path) -> list:
        cfg = config_manager.config
        cmd = [
            str(aria2c_file.absolute()),
            "--enable-rpc=true",
            f"--rpc-listen-port={cfg.aria2_rpc_port}",
            "--rpc-listen-all=false",
            "--save-session-interval=30",
            f"--max-concurrent-downloads={cfg.max_concurrent_downloads}",
            f"--max-connection-per-server={cfg.default_connections}",
            "--min-split-size=10M",
            f"--split={cfg.default_splits}",
            f"--dir={config_manager.ensure_downloads_dir()}",
            "--file-allocation=none",
            "--continue=true",
            "--auto-file-renaming=true",
            "--allow-overwrite=false",
            "--max-tries=3",
            "--retry-wait=10",
            "--disable-ipv6=true",
            "--remote-time=true",
            "--summary-interval=0",
            "--console-log-level=warn",
            "--bt-stop-timeout=0",
            # BT / 做种
            "--bt-save-metadata=true",           # 磁力任务自动保存 .torrent 元数据
            "--follow-torrent=mem",
            f"--listen-port={cfg.bt_listen_port}",
            f"--enable-dht={'true' if cfg.bt_enable_dht else 'false'}",
            f"--seed-ratio={cfg.bt_seed_ratio}",
            f"--seed-time={cfg.bt_seed_time}",
        ]
        if cfg.bt_trackers:
            # 每行一个 tracker，aria2 以逗号分隔接收
            trackers = ",".join(
                t.strip() for t in cfg.bt_trackers.splitlines() if t.strip()
            )
            if trackers:
                cmd.append(f"--bt-tracker={trackers}")
        if cfg.max_overall_download_limit:
            cmd.append(f"--max-overall-download-limit={cfg.max_overall_download_limit}")
        if cfg.aria2_rpc_secret:
            cmd.append(f"--rpc-secret={cfg.aria2_rpc_secret}")

        session_file = config_manager.session_file
        if session_file.exists():
            cmd.append(f"--input-file={session_file}")
            logger.info("加载会话文件: %s", session_file)
        cmd.append(f"--save-session={session_file}")
        return cmd

    def stop(self):
        """停止 aria2c：先 RPC 优雅关闭（保存会话），超时再强杀

        即使 aria2c 是复用的外部实例，也尝试 RPC 优雅关闭，
        保证"关闭本程序 = 不遗留下载引擎进程"。
        """
        with self._state_lock:
            self._stop_health.set()
            process = self.process
            self.process = None
            self.external = False

        # 优雅关闭（对外部复用的实例同样生效）
        try:
            if aria2_client.ping():
                logger.info("正在停止 aria2c（RPC 优雅关闭）...")
                aria2_client.shutdown()
        except Exception as e:
            logger.warning("RPC shutdown 调用失败: %s", e)

        if process is None:
            # 外部实例已通过 RPC 关闭，无需（也不能）强杀
            self._close_job()
            self._close_log()
            return

        try:
            proc = psutil.Process(process.pid)
            try:
                proc.wait(timeout=5)
                logger.info("aria2c 已优雅退出，会话已保存")
            except psutil.TimeoutExpired:
                logger.warning("aria2c 优雅退出超时，强制结束")
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            logger.warning("停止 aria2c 时出错: %s", e)
        self._close_job()
        self._close_log()

    def _close_job(self):
        """关闭 Job Object 句柄（若 aria2c 仍在运行则由内核终止）"""
        if self._job_handle is not None:
            try:
                ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self._job_handle))
            except Exception:
                pass
            self._job_handle = None

    # ---------- 状态 ----------

    def is_rpc_alive(self) -> bool:
        return aria2_client.ping()

    def is_running(self) -> bool:
        if self.process is not None and self.process.poll() is None:
            return True
        return self.is_rpc_alive()

    def _port_in_use(self) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(1)
            return sock.connect_ex(("127.0.0.1", config_manager.config.aria2_rpc_port)) == 0
        finally:
            sock.close()

    def _wait_for_rpc(self, timeout: int) -> bool:
        deadline = time.time() + timeout
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            if self.process is not None and self.process.poll() is not None:
                return False  # 进程已退出，无需继续等待
            if aria2_client.ping():
                logger.info("RPC 服务就绪（第 %d 次探测）", attempt)
                return True
            time.sleep(0.5)
        return False

    # ---------- 健康检查 ----------

    def _start_health_check(self):
        if self._health_thread is not None and self._health_thread.is_alive():
            return
        self._stop_health.clear()
        self._health_thread = threading.Thread(
            target=self._health_loop, name="aria2-health", daemon=True
        )
        self._health_thread.start()

    def _health_loop(self):
        """每 10 秒探活一次；进程意外退出时自动重启（有次数上限）"""
        ext_dead_cycles = 0
        while not self._stop_health.is_set():
            self._stop_health.wait(10)
            if self._stop_health.is_set():
                break
            try:
                if self.is_rpc_alive():
                    self._restart_count = 0
                    ext_dead_cycles = 0
                    continue

                # RPC 不可达：若我们自己启动的进程已退出，尝试重启
                if self.process is not None and self.process.poll() is not None:
                    logger.warning("aria2c 进程已退出（code=%s）", self.process.returncode)
                    if self._restart_count < self._max_restart:
                        self._restart_count += 1
                        logger.info("尝试第 %d 次自动重启 aria2c", self._restart_count)
                        with self._state_lock:
                            self.process = None
                        try:
                            self.start()
                        except Exception as e:
                            logger.error("自动重启失败: %s", e)
                    else:
                        logger.error("aria2c 多次退出，停止自动重启，请查看日志")
                        self._stop_health.set()
                elif self.process is None:
                    # 复用的外部 aria2c 消失了（或启动失败），连续两个周期不可达后自行拉起
                    ext_dead_cycles += 1
                    if ext_dead_cycles >= 2:
                        logger.warning("aria2c RPC 持续不可达，尝试自行启动")
                        ext_dead_cycles = 0
                        try:
                            self.start()
                        except Exception as e:
                            logger.error("自动拉起 aria2c 失败: %s", e)
                else:
                    logger.warning("aria2c RPC 暂时不可达，将在下个周期重试")
            except Exception as e:
                logger.error("健康检查异常: %s", e)

    # ---------- 日志 ----------

    def _read_log_tail(self, lines: int = 15) -> str:
        try:
            log_path = config_manager.log_dir / "aria2c.log"
            if not log_path.exists():
                return ""
            content = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            tail = [l for l in content[-lines:] if l.strip()]
            return "日志尾部: " + " | ".join(tail[-5:]) if tail else ""
        except Exception:
            return ""

    def _close_log(self):
        if self._log_file is not None:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None


def mask_secret(cmd: list) -> list:
    """日志中隐藏 RPC 密钥"""
    return [
        ("--rpc-secret=***" if str(a).startswith("--rpc-secret=") else a) for a in cmd
    ]


aria2_manager = Aria2ProcessManager()
