import requests
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from .config import config_manager
from .models import DownloadTask, DownloadTaskCreate, TaskStatus, GlobalStats


def log_with_time(message):
    """打印带时间戳的日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


class Aria2Client:
    """aria2 RPC 客户端"""
    
    def __init__(self):
        self._rpc_url = None
        self._rpc_secret = None
        self.request_id = 0
        
    @property
    def rpc_url(self):
        if self._rpc_url is None:
            self._rpc_url = config_manager.get_rpc_url()
        return self._rpc_url
        
    @property
    def rpc_secret(self):
        if self._rpc_secret is None:
            self._rpc_secret = config_manager.config.aria2_rpc_secret
        return self._rpc_secret
        
    def _call(self, method: str, params: List[Any] = None, retries: int = 3, timeout: int = 15) -> Optional[Any]:
        """调用 aria2 RPC 方法"""
        self.request_id += 1
        
        # 构建参数
        rpc_params = []
        if self.rpc_secret:
            rpc_params.append(f"token:{self.rpc_secret}")
        if params:
            rpc_params.extend(params)
        
        payload = {
            "jsonrpc": "2.0",
            "id": str(self.request_id),
            "method": method,
            "params": rpc_params
        }
        
        # 重试机制
        for attempt in range(retries):
            try:
                response = requests.post(
                    self.rpc_url,
                    json=payload,
                    timeout=timeout  # 使用自定义超时时间
                )
                response.raise_for_status()
                result = response.json()
                
                if "error" in result:
                    # 只在出错时打印
                    if method not in ["aria2.tellActive", "aria2.tellWaiting", "aria2.tellStopped", "aria2.getGlobalStat"]:
                        log_with_time(f"RPC 错误: {result['error']}")
                    return None
                
                return result.get("result")
            except requests.exceptions.Timeout:
                log_with_time(f"RPC 调用超时 ({method})")
                if attempt < retries - 1:
                    log_with_time(f"重试中... ({attempt + 1}/{retries})")
                    import time
                    time.sleep(1)  # 等待1秒后重试
                    continue
                else:
                    log_with_time(f"RPC 调用超时，已达到最大重试次数")
                    return None
            except requests.exceptions.ConnectionError as e:
                log_with_time(f"RPC 连接错误: {e}")
                # 连接错误可能是 aria2c 崩溃了，尝试重新启动
                if attempt == retries - 1:
                    log_with_time("尝试重新启动 aria2c...")
                    from .aria2_process import aria2_manager
                    try:
                        aria2_manager.stop()
                        time.sleep(1)
                        if aria2_manager.start():
                            log_with_time("aria2c 重新启动成功，重试 RPC 调用")
                            continue
                    except Exception as restart_error:
                        log_with_time(f"重新启动 aria2c 失败: {restart_error}")
                return None
            except Exception as e:
                # 只在非查询操作时打印错误
                if method not in ["aria2.tellActive", "aria2.tellWaiting", "aria2.tellStopped", "aria2.getGlobalStat"]:
                    log_with_time(f"RPC 调用失败: {e}")
                return None
        
        return None
    
    def add_task(self, task_create: DownloadTaskCreate) -> Optional[str]:
        """添加下载任务"""
        log_with_time(f"添加任务: urls={task_create.urls}, save_dir={task_create.save_dir}")
        
        # 确定保存目录
        save_dir = task_create.save_dir or config_manager.config.default_download_dir
        
        # 构建选项
        options = {
            "dir": save_dir,
            "max-connection-per-server": task_create.connections,
            "split": task_create.splits,
            "min-split-size": "1M",
        }
        
        # 自定义文件名
        if task_create.filename:
            options["out"] = task_create.filename
            
        # 单任务限速
        if task_create.max_speed:
            options["max-download-limit"] = self._parse_speed(task_create.max_speed)
        
        log_with_time(f"调用 aria2.addUri，选项: {options}")
        
        # 调用 aria2.addUri，使用较短的超时时间5秒，只重试1次
        result = self._call("aria2.addUri", [task_create.urls, options], retries=1, timeout=5)
        
        log_with_time(f"aria2.addUri 结果: {result}")
        return result  # 返回 gid
    
    def _parse_speed(self, speed: str) -> str:
        """解析速度字符串为 aria2 格式"""
        speed = speed.upper().strip()
        if speed.endswith("K"):
            return str(int(float(speed[:-1]) * 1024))
        elif speed.endswith("M"):
            return str(int(float(speed[:-1]) * 1024 * 1024))
        elif speed.endswith("G"):
            return str(int(float(speed[:-1]) * 1024 * 1024 * 1024))
        return speed
    
    def get_task(self, gid: str) -> Optional[DownloadTask]:
        """获取单个任务信息"""
        result = self._call("aria2.tellStatus", [gid])
        if not result:
            return None
        return self._parse_task(result)
    
    def get_active_tasks(self) -> List[DownloadTask]:
        """获取活动任务列表"""
        result = self._call("aria2.tellActive")
        if not result:
            return []
        return [self._parse_task(t) for t in result]
    
    def get_waiting_tasks(self) -> List[DownloadTask]:
        """获取等待任务列表"""
        result = self._call("aria2.tellWaiting", [0, 100])
        if not result:
            return []
        return [self._parse_task(t) for t in result]
    
    def get_stopped_tasks(self) -> List[DownloadTask]:
        """获取已停止任务列表"""
        result = self._call("aria2.tellStopped", [0, 100])
        if not result:
            return []
        return [self._parse_task(t) for t in result]
    
    def get_all_tasks(self) -> List[DownloadTask]:
        """获取所有任务"""
        tasks = []
        tasks.extend(self.get_active_tasks())
        tasks.extend(self.get_waiting_tasks())
        tasks.extend(self.get_stopped_tasks())
        return tasks
    
    def pause_task(self, gid: str) -> bool:
        """暂停任务"""
        log_with_time(f"暂停任务: gid={gid}")
        result = self._call("aria2.pause", [gid])
        log_with_time(f"暂停结果: {result}")
        return result is not None
    
    def pause_all(self) -> bool:
        """暂停所有任务"""
        result = self._call("aria2.pauseAll")
        return result is not None
    
    def resume_task(self, gid: str) -> bool:
        """继续任务"""
        log_with_time(f"继续任务: gid={gid}")
        result = self._call("aria2.unpause", [gid])
        log_with_time(f"继续结果: {result}")
        return result is not None
    
    def resume_all(self) -> bool:
        """继续所有任务"""
        result = self._call("aria2.unpauseAll")
        return result is not None
    
    def remove_task(self, gid: str) -> bool:
        """删除任务"""
        log_with_time(f"删除任务: gid={gid}")
        
        # 先尝试从活动/等待列表中移除
        result = self._call("aria2.remove", [gid])
        if result:
            log_with_time(f"从活动列表删除成功: {result}")
            return True
        
        # 如果失败，尝试从已停止列表中移除
        result = self._call("aria2.removeDownloadResult", [gid])
        if result:
            log_with_time(f"从已停止列表删除成功: {result}")
            return True
        
        log_with_time(f"删除失败")
        return False
    
    def get_global_stats(self) -> GlobalStats:
        """获取全局统计"""
        result = self._call("aria2.getGlobalStat")
        if not result:
            return GlobalStats()
        
        return GlobalStats(
            download_speed=int(result.get("downloadSpeed", 0)),
            upload_speed=int(result.get("uploadSpeed", 0)),
            num_active=int(result.get("numActive", 0)),
            num_waiting=int(result.get("numWaiting", 0)),
            num_stopped=int(result.get("numStopped", 0))
        )
    
    def _parse_task(self, data: Dict[str, Any]) -> DownloadTask:
        """解析 aria2 任务数据"""
        gid = data.get("gid", "")
        status_str = data.get("status", "error")
        
        # 映射状态
        status_map = {
            "active": TaskStatus.ACTIVE,
            "waiting": TaskStatus.WAITING,
            "paused": TaskStatus.PAUSED,
            "error": TaskStatus.ERROR,
            "complete": TaskStatus.COMPLETE,
            "removed": TaskStatus.REMOVED,
        }
        status = status_map.get(status_str, TaskStatus.ERROR)
        
        # 计算进度
        total_length = int(data.get("totalLength", 0))
        completed_length = int(data.get("completedLength", 0))
        progress = (completed_length / total_length * 100) if total_length > 0 else 0
        
        # 获取下载速度
        download_speed = int(data.get("downloadSpeed", 0))
        
        # 获取连接数信息
        connections = 0
        if "connections" in data:
            connections = int(data.get("connections", 0))
        
        # 获取分片数
        splits = 0
        if "numPieces" in data:
            splits = int(data.get("numPieces", 0))
        
        # 获取错误信息
        error_message = None
        if status == TaskStatus.ERROR:
            error_message = data.get("errorMessage", "未知错误")
        
        # 获取文件信息
        files = data.get("files", [])
        urls = []
        if files and len(files) > 0:
            uris = files[0].get("uris", [])
            urls = [u.get("uri", "") for u in uris if u.get("uri")]
        
        # 获取保存目录和文件名
        save_dir = data.get("dir", "")
        filename = None
        if files and len(files) > 0:
            path = files[0].get("path", "")
            if path:
                filename = path.split("/")[-1].split("\\")[-1]
        
        # 获取选项中的连接数和分片数
        options = data.get("options", {})
        opt_connections = int(options.get("max-connection-per-server", 16))
        opt_splits = int(options.get("split", 16))
        
        return DownloadTask(
            gid=gid,
            urls=urls,
            save_dir=save_dir,
            filename=filename,
            status=status,
            total_length=total_length,
            completed_length=completed_length,
            download_speed=download_speed,
            connections=connections or opt_connections,
            splits=splits or opt_splits,
            progress=round(progress, 2),
            error_message=error_message,
            created_at=datetime.now(),  # aria2 不直接提供创建时间
            completed_at=datetime.now() if status == TaskStatus.COMPLETE else None
        )


# 全局客户端实例
aria2_client = Aria2Client()