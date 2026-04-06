import subprocess
import time
import psutil
import requests
from pathlib import Path
from typing import Optional
import atexit
import threading
from datetime import datetime

from .config import config_manager


def log_with_time(message):
    """打印带时间戳的日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


class Aria2ProcessManager:
    """aria2c 进程管理器"""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.rpc_url = config_manager.get_rpc_url()
        self.rpc_port = config_manager.config.aria2_rpc_port
        self.aria2c_path = config_manager.get_aria2c_path()
        self.session_file = config_manager.app_dir / "aria2.session"
        self._health_check_thread: Optional[threading.Thread] = None
        self._stop_health_check = threading.Event()
        self._consecutive_failures = 0
        
    def start(self) -> bool:
        """启动 aria2c 守护进程"""
        log_with_time("尝试启动 aria2c...")
        log_with_time(f"aria2c 路径: {self.aria2c_path}")
        
        if self.is_running():
            log_with_time("aria2c 已经在运行")
            return True
            
        # 确保 aria2c 存在
        aria2c_file = Path(self.aria2c_path)
        if not aria2c_file.exists():
            error_msg = f"找不到 aria2c: {self.aria2c_path}"
            log_with_time(error_msg)
            raise FileNotFoundError(error_msg)
        
        log_with_time(f"找到 aria2c: {aria2c_file.absolute()}")
        
        # 确保下载目录存在
        downloads_dir = config_manager.ensure_downloads_dir()
        log_with_time(f"下载目录: {downloads_dir}")
        
        # 构建启动参数 - 简化版本
        cmd = [
            str(aria2c_file.absolute()),
            "--enable-rpc=true",
            f"--rpc-listen-port={self.rpc_port}",
            "--rpc-allow-origin-all=true",
            "--rpc-listen-all=false",
            "--rpc-max-request-size=1024M",
            "--save-session-interval=0",  # 禁用定期保存会话，减少冲突
            # 移除 --force-save=true，避免暂停时死锁
            "--log-level=debug",
            f"--max-concurrent-downloads={config_manager.config.max_concurrent_downloads}",
            "--max-connection-per-server=16",
            "--min-split-size=1M",
            "--split=16",
            f"--dir={downloads_dir}",
            "--file-allocation=none",  # 改为 none，避免预分配问题
            "--continue=true",
            "--auto-file-renaming=true",
            "--allow-overwrite=false",
            "--max-tries=3",
            "--retry-wait=10",
            "--max-file-not-found=3",
            "--disable-ipv6=true",
            "--remote-time=true",
            "--summary-interval=0",
            "--console-log-level=warn",
            "--bt-stop-timeout=0",  # BT 停止时不等待，避免卡死
        ]
        
        # 添加会话文件（如果存在）
        if self.session_file.exists():
            cmd.append(f"--input-file={self.session_file}")
            log_with_time(f"加载会话文件: {self.session_file}")
        else:
            log_with_time("会话文件不存在，将创建新的会话文件")
        cmd.append(f"--save-session={self.session_file}")
        
        # 添加密钥（如果配置了）
        if config_manager.config.aria2_rpc_secret:
            cmd.append(f"--rpc-secret={config_manager.config.aria2_rpc_secret}")
        
        log_with_time(f"启动命令: {' '.join(cmd)}")
        
        try:
            # 启动进程
            creationflags = 0
            if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                creationflags = subprocess.CREATE_NO_WINDOW
            
            # 打开日志文件，带时间戳前缀
            log_file = open(self.session_file.parent / "aria2c.log", "w")
            
            # 写入启动时间
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            log_file.write(f"[{start_time}] aria2c 启动\n")
            log_file.flush()
            
            self.process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,  # 合并错误到标准输出
                creationflags=creationflags
            )
            
            log_with_time(f"进程已启动，PID: {self.process.pid}")
            
            # 等待一小段时间让进程初始化
            time.sleep(1)
            
            # 检查进程是否还在运行
            if self.process.poll() is not None:
                # 进程已经退出，读取错误信息
                stdout, stderr = self.process.communicate()
                error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "未知错误"
                log_with_time(f"aria2c 启动失败，错误: {error_msg}")
                raise RuntimeError(f"aria2c 启动失败: {error_msg}")
            
            # 等待 RPC 服务启动
            log_with_time("等待 RPC 服务启动...")
            if self._wait_for_rpc(timeout=15):
                log_with_time(f"aria2c 启动成功，PID: {self.process.pid}")
                # # 注册退出时清理
                # atexit.register(self.stop)
                # return True
            
                # 延迟 30 秒再启动健康检查，给 aria2c 充分初始化时间
                def delayed_health_check():
                    time.sleep(30)
                    self.start_health_check()
                threading.Thread(target=delayed_health_check, daemon=True).start()
                return True
            else:
                # 超时，尝试获取错误信息
                stdout, stderr = self.process.communicate(timeout=1)
                error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "RPC 服务启动超时"
                log_with_time(f"aria2c RPC 启动失败: {error_msg}")
                self.stop()
                raise RuntimeError(f"aria2c RPC 服务启动超时: {error_msg}")
                
        except Exception as e:
            log_with_time(f"启动 aria2c 异常: {e}")
            raise RuntimeError(f"启动 aria2c 失败: {e}")
    
    def stop(self):
        """停止 aria2c 进程"""
        log_with_time("停止 aria2c 进程...")
        if self.process:
            try:
                # 尝试优雅关闭
                try:
                    parent = psutil.Process(self.process.pid)
                    for child in parent.children(recursive=True):
                        child.terminate()
                    parent.terminate()
                    
                    # 等待进程结束
                    gone, alive = psutil.wait_procs([parent], timeout=3)
                    if alive:
                        # 强制结束
                        for p in alive:
                            p.kill()
                except psutil.NoSuchProcess:
                    pass
                        
            except Exception as e:
                log_with_time(f"停止 aria2c 时出错: {e}")
            finally:
                self.process = None
                log_with_time("aria2c 已停止")
    
    def is_running(self) -> bool:
        """检查 aria2c 是否正在运行"""
        if self.process is not None:
            # 检查我们启动的进程是否还在运行
            return self.process.poll() is None
        
        # 检查是否有其他 aria2c 进程在使用相同端口
        if self._check_port_in_use():
            # 端口被占用，尝试连接 RPC 确认服务是否真的可用
            try:
                response = requests.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": "test",
                        "method": "aria2.getVersion",
                        "params": []
                    },
                    timeout=5
                )
                if response.status_code == 200:
                    log_with_time("检测到已运行的 aria2c RPC 服务")
                    return True
            except Exception as e:
                log_with_time(f"端口被占用但 RPC 不可用: {e}")
            
            # 端口被占用但 RPC 不可用，可能是僵尸进程，尝试清理
            log_with_time(f"端口 {self.rpc_port} 被占用但 RPC 不可用，尝试清理...")
            self._kill_process_on_port()
            return False
        
        return False
    
    def _kill_process_on_port(self):
        """清理占用端口的进程"""
        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == self.rpc_port and conn.pid:
                    log_with_time(f"找到占用端口 {self.rpc_port} 的进程: {conn.pid}")
                    try:
                        proc = psutil.Process(conn.pid)
                        proc.terminate()
                        proc.wait(timeout=3)
                        log_with_time(f"已终止进程 {conn.pid}")
                    except psutil.NoSuchProcess:
                        pass
                    except Exception as e:
                        log_with_time(f"终止进程失败: {e}")
                        try:
                            proc.kill()
                        except:
                            pass
        except Exception as e:
            log_with_time(f"清理端口时出错: {e}")
    
    def _check_port_in_use(self) -> bool:
        """检查端口是否被占用"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', self.rpc_port))
            sock.close()
            if result == 0:
                log_with_time(f"端口 {self.rpc_port} 已被占用")
            return result == 0
        except Exception as e:
            log_with_time(f"检查端口时出错: {e}")
            return False
    
    def _wait_for_rpc(self, timeout: int = 15) -> bool:
        """等待 RPC 服务可用"""
        start_time = time.time()
        attempt = 0
        while time.time() - start_time < timeout:
            attempt += 1
            try:
                response = requests.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": "test",
                        "method": "aria2.getVersion",
                        "params": []
                    },
                    timeout=5
                )
                if response.status_code == 200:
                    log_with_time(f"RPC 服务响应成功 (尝试 {attempt} 次)")
                    return True
            except requests.exceptions.ConnectionError:
                pass
            except requests.exceptions.Timeout:
                log_with_time(f"RPC 检查超时 (尝试 {attempt} 次)")
            except Exception as e:
                log_with_time(f"RPC 检查异常: {e}")
            time.sleep(0.5)
        
        log_with_time(f"RPC 服务启动超时 (尝试了 {attempt} 次)")
        return False
    
    def start_health_check(self):
        """启动健康检查线程"""
        if self._health_check_thread is not None and self._health_check_thread.is_alive():
            return
        
        self._stop_health_check.clear()
        self._health_check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self._health_check_thread.start()
        log_with_time("健康检查线程已启动")
    
    def stop_health_check(self):
        """停止健康检查线程"""
        self._stop_health_check.set()
        if self._health_check_thread:
            self._health_check_thread.join(timeout=2)
            log_with_time("健康检查线程已停止")
    
    def _health_check_loop(self):
        """健康检查循环"""
        while not self._stop_health_check.is_set():
            try:
                # 每 30 秒检查一次
                time.sleep(30)
                
                # 尝试 ping aria2c
                try:
                    response = requests.post(
                        self.rpc_url,
                        json={
                            "jsonrpc": "2.0",
                            "id": "health",
                            "method": "aria2.getVersion",
                            "params": []
                        },
                        timeout=20
                    )
                    
                    if response.status_code == 200:
                        # 健康检查成功，重置失败计数
                        if self._consecutive_failures > 0:
                            log_with_time(f"aria2c 恢复健康 (之前失败 {self._consecutive_failures} 次)")
                            self._consecutive_failures = 0
                    else:
                        self._consecutive_failures += 1
                        log_with_time(f"健康检查失败 (状态码: {response.status_code})，连续失败 {self._consecutive_failures} 次")
                        
                except Exception as e:
                    self._consecutive_failures += 1
                    log_with_time(f"健康检查异常: {e}，连续失败 {self._consecutive_failures} 次")
                
                # 禁用自动重启，只记录日志
                if self._consecutive_failures >= 5:
                    log_with_time("连续 5 次健康检查失败，请手动检查 aria2c 状态")
                    # 重置计数器，避免重复打印
                    self._consecutive_failures = 0
                        
            except Exception as e:
                log_with_time(f"健康检查循环异常: {e}")
                time.sleep(5)


# 全局进程管理器实例
aria2_manager = Aria2ProcessManager()
