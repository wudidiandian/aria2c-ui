import httpx
import json
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

from .config import config_manager
from .models import DownloadTask, DownloadTaskCreate, TaskStatus, GlobalStats


def log_with_time(message):
    """打印带时间戳的日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


class Aria2Client:
    """aria2 RPC 客户端 (异步版)"""
    
    def __init__(self):
        self._rpc_url = None
        self._rpc_secret = None
        self.request_id = 0
        self._client: Optional[httpx.AsyncClient] = None
        
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

    async def get_client(self) -> httpx.AsyncClient:
        """获取异步 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self):
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        
    async def _call(self, method: str, params: List[Any] = None, retries: int = 1, timeout: float = 5.0) -> Optional[Any]:
        """调用 aria2 RPC 方法 (异步)"""
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
        
        # 对于查询类操作，进一步压缩超时和重试
        is_query = method in ["aria2.tellActive", "aria2.tellWaiting", "aria2.tellStopped", "aria2.getGlobalStat"]
        if is_query:
            timeout = 2.0
            retries = 0

        client = await self.get_client()
        
        for attempt in range(retries + 1):
            try:
                response = await client.post(
                    self.rpc_url,
                    json=payload,
                    timeout=timeout
                )
                response.raise_for_status()
                result = response.json()
                
                if "error" in result:
                    if not is_query:
                        log_with_time(f"RPC 错误: {result['error']}")
                    return None
                
                return result.get("result")
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < retries:
                    await asyncio.sleep(0.5)
                    continue
                if not is_query:
                    log_with_time(f"RPC 调用失败 ({method}): {e}")
                return None
            except Exception as e:
                if not is_query:
                    log_with_time(f"RPC 异常 ({method}): {e}")
                return None
        
        return None
    
    async def add_task(self, task_create: DownloadTaskCreate) -> Optional[str]:
        """添加下载任务"""
        log_with_time(f"添加任务: urls={task_create.urls}, save_dir={task_create.save_dir}")
        
        save_dir = task_create.save_dir or config_manager.config.default_download_dir
        
        options = {
            "dir": save_dir,
            "max-connection-per-server": str(task_create.connections),
            "split": str(task_create.splits),
            "min-split-size": "1M",
        }
        
        if task_create.filename:
            options["out"] = task_create.filename
            
        if task_create.max_speed:
            options["max-download-limit"] = self._parse_speed(task_create.max_speed)
        
        result = await self._call("aria2.addUri", [task_create.urls, options], retries=1, timeout=5.0)
        log_with_time(f"aria2.addUri 结果: {result}")
        return result
    
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
    
    async def get_task(self, gid: str) -> Optional[DownloadTask]:
        """获取单个任务信息"""
        result = await self._call("aria2.tellStatus", [gid])
        if not result:
            return None
        return self._parse_task(result)
    
    async def get_active_tasks(self) -> List[DownloadTask]:
        """获取活动任务列表"""
        result = await self._call("aria2.tellActive")
        if not result:
            return []
        return [self._parse_task(t) for t in result]
    
    async def get_waiting_tasks(self) -> List[DownloadTask]:
        """获取等待任务列表"""
        result = await self._call("aria2.tellWaiting", [0, 100])
        if not result:
            return []
        return [self._parse_task(t) for t in result]
    
    async def get_stopped_tasks(self) -> List[DownloadTask]:
        """获取已停止任务列表"""
        result = await self._call("aria2.tellStopped", [0, 100])
        if not result:
            return []
        return [self._parse_task(t) for t in result]
    
    async def get_all_tasks(self) -> List[DownloadTask]:
        """获取所有任务 (并发查询)"""
        # 使用 asyncio.gather 并发执行三个查询
        active_task = self.get_active_tasks()
        waiting_task = self.get_waiting_tasks()
        stopped_task = self.get_stopped_tasks()
        
        results = await asyncio.gather(active_task, waiting_task, stopped_task, return_exceptions=True)
        
        tasks = []
        for res in results:
            if isinstance(res, list):
                tasks.extend(res)
        return tasks
    
    async def pause_task(self, gid: str) -> bool:
        """暂停任务"""
        result = await self._call("aria2.pause", [gid])
        return result is not None
    
    async def pause_all(self) -> bool:
        """暂停所有任务"""
        result = await self._call("aria2.pauseAll")
        return result is not None
    
    async def resume_task(self, gid: str) -> bool:
        """继续任务"""
        result = await self._call("aria2.unpause", [gid])
        return result is not None
    
    async def resume_all(self) -> bool:
        """继续所有任务"""
        result = await self._call("aria2.unpauseAll")
        return result is not None
    
    async def remove_task(self, gid: str) -> bool:
        """删除任务"""
        # 先尝试从活动/等待列表中移除
        result = await self._call("aria2.remove", [gid])
        if result:
            return True
        
        # 如果失败，尝试从已停止列表中移除
        result = await self._call("aria2.removeDownloadResult", [gid])
        return result is not None
    
    async def get_global_stats(self) -> GlobalStats:
        """获取全局统计"""
        result = await self._call("aria2.getGlobalStat")
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
        """解析 aria2 任务数据 (保持同步解析)"""
        gid = data.get("gid", "")
        status_str = data.get("status", "error")
        
        status_map = {
            "active": TaskStatus.ACTIVE,
            "waiting": TaskStatus.WAITING,
            "paused": TaskStatus.PAUSED,
            "error": TaskStatus.ERROR,
            "complete": TaskStatus.COMPLETE,
            "removed": TaskStatus.REMOVED,
        }
        status = status_map.get(status_str, TaskStatus.ERROR)
        
        total_length = int(data.get("totalLength", 0))
        completed_length = int(data.get("completedLength", 0))
        progress = (completed_length / total_length * 100) if total_length > 0 else 0
        
        download_speed = int(data.get("downloadSpeed", 0))
        
        connections = int(data.get("connections", 0))
        splits = int(data.get("numPieces", 0))
        
        error_message = data.get("errorMessage") if status == TaskStatus.ERROR else None
        
        files = data.get("files", [])
        urls = []
        filename = None
        if files:
            uris = files[0].get("uris", [])
            urls = [u.get("uri", "") for u in uris if u.get("uri")]
            path = files[0].get("path", "")
            if path:
                filename = path.split("/")[-1].split("\\")[-1]
        
        options = data.get("options", {})
        opt_connections = int(options.get("max-connection-per-server", 16))
        opt_splits = int(options.get("split", 16))
        
        return DownloadTask(
            gid=gid,
            urls=urls,
            save_dir=data.get("dir", ""),
            filename=filename,
            status=status,
            total_length=total_length,
            completed_length=completed_length,
            download_speed=download_speed,
            connections=connections or opt_connections,
            splits=splits or opt_splits,
            progress=round(progress, 2),
            error_message=error_message,
            created_at=datetime.now(),
            completed_at=datetime.now() if status == TaskStatus.COMPLETE else None
        )


# 全局客户端实例
aria2_client = Aria2Client()
