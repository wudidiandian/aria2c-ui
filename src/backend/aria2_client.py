import re
import time
import base64
import threading
from typing import List, Optional, Dict, Any
from urllib.parse import urlsplit, parse_qs, unquote

import requests

from .config import config_manager
from .models import DownloadTask, DownloadTaskCreate, TaskStatus, GlobalStats

# 单次 RPC 超时（本地进程，不需要长超时）
RPC_TIMEOUT = 5.0
# tellWaiting / tellStopped 单页大小，分页拉取避免超过 100 条被截断
PAGE_SIZE = 500
MAX_PAGES = 4


class Aria2Error(Exception):
    """aria2 RPC 调用失败（携带可展示给用户的信息）"""

    def __init__(self, message: str, code: Optional[int] = None):
        super().__init__(message)
        self.code = code


class Aria2Unavailable(Aria2Error):
    """aria2c RPC 不可达"""


class Aria2Client:
    """aria2 JSON-RPC 客户端（同步版，供 pywebview API 线程与推送线程使用）"""

    def __init__(self):
        self._session: Optional[requests.Session] = None
        self._request_id = 0
        self._lock = threading.Lock()
        # 磁力任务名称提示：tellStatus 在元数据获取完成前没有文件名，
        # 用创建时的 magnet dn 参数兜底显示（内存态，足够覆盖下载周期）
        self._name_hints: Dict[str, str] = {}

    def _get_session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def close(self):
        if self._session is not None:
            self._session.close()
            self._session = None

    # ---------- RPC 基础 ----------

    def call(self, method: str, params: Optional[List[Any]] = None,
             retries: int = 1, timeout: float = RPC_TIMEOUT) -> Any:
        """调用 aria2 RPC 方法，失败抛出 Aria2Error"""
        rpc_params: List[Any] = []
        secret = config_manager.config.aria2_rpc_secret
        if secret:
            rpc_params.append(f"token:{secret}")
        if params:
            rpc_params.extend(params)

        with self._lock:
            self._request_id += 1
            request_id = self._request_id

        payload = {
            "jsonrpc": "2.0",
            "id": str(request_id),
            "method": method,
            "params": rpc_params,
        }

        for attempt in range(retries + 1):
            try:
                response = self._get_session().post(
                    config_manager.get_rpc_url(), json=payload, timeout=timeout
                )
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt < retries:
                    time.sleep(0.3)
                    continue
                raise Aria2Unavailable(f"无法连接 aria2c（{method}）") from e

            # 注意：aria2 对应用级错误也返回非 200（如 400），但 body 带 JSON-RPC 错误信息，
            # 必须先解析 body，不能先 raise_for_status
            try:
                result = response.json()
            except ValueError as e:
                raise Aria2Error(
                    f"RPC 响应异常（{method}）: HTTP {response.status_code}"
                ) from e

            if "error" in result:
                err = result["error"]
                raise Aria2Error(err.get("message", "未知 RPC 错误"), code=err.get("code"))
            return result.get("result")

        raise Aria2Unavailable(f"无法连接 aria2c（{method}）")

    def ping(self) -> bool:
        """轻量探活"""
        try:
            self.call("aria2.getVersion", retries=0, timeout=2.0)
            return True
        except Aria2Error:
            return False

    def get_version(self) -> dict:
        result = self.call("aria2.getVersion")
        return {
            "version": result.get("version", "unknown"),
            "enabled_features": result.get("enabledFeatures", []),
        }

    def change_global_option(self, options: Dict[str, str]) -> None:
        """修改 aria2 全局选项（立即生效）"""
        self.call("aria2.changeGlobalOption", [options])

    # ---------- 任务操作 ----------

    def add_task(self, task_create: DownloadTaskCreate) -> List[str]:
        """添加下载任务。每个 URL 一个独立任务，返回 gid 列表。"""
        cfg = config_manager.config
        save_dir = task_create.save_dir or cfg.default_download_dir
        # 未显式指定时使用全局配置（设置修改后对新建任务立即生效，无需重启）
        connections = task_create.connections if task_create.connections is not None else cfg.default_connections
        splits = task_create.splits if task_create.splits is not None else cfg.default_splits

        base_options = {
            "dir": save_dir,
            "max-connection-per-server": str(connections),
            "split": str(splits),
            "min-split-size": "10M",
        }
        if task_create.max_speed:
            base_options["max-download-limit"] = self._parse_speed(task_create.max_speed)

        gids: List[str] = []
        for i, url in enumerate(task_create.urls):
            options = dict(base_options)
            is_magnet = url.strip().lower().startswith("magnet:")
            # BT 任务不支持 out 参数（多文件），且磁力链接不能指定文件名
            if task_create.filename and len(task_create.urls) == 1 and not is_magnet:
                options["out"] = task_create.filename
            try:
                gid = self.call("aria2.addUri", [[url], options])
            except Aria2Error:
                # 前面已成功的任务保留，失败的 URL 抛给前端提示
                if gids:
                    raise Aria2Error(
                        f"已创建 {len(gids)} 个任务，但第 {len(gids) + 1} 个链接创建失败"
                    )
                raise
            if gid:
                gids.append(gid)
                if is_magnet:
                    self._name_hints[gid] = self._magnet_display_name(url)

        if not gids:
            raise Aria2Error("创建任务失败")
        return gids

    @staticmethod
    def _magnet_display_name(url: str) -> str:
        """从磁力链接提取展示名：dn 参数 > btih 哈希前缀"""
        try:
            query = parse_qs(urlsplit(url).query)
            dn = query.get("dn", [None])[0]
            if dn:
                return unquote(dn)
        except ValueError:
            pass
        match = re.search(r"urn:btih:([0-9A-Za-z]+)", url)
        if match:
            return f"BT 磁力任务 ({match.group(1)[:12]})"
        return "BT 磁力任务"

    def add_torrent(self, torrent_path: str, save_dir: Optional[str] = None) -> str:
        """添加 .torrent 种子文件任务，返回 gid。

        种子内即使包含多个文件，aria2 也按一个任务处理（文件保存在
        save_dir/<种子名>/ 下）。BT 任务不支持 out 参数重命名。
        """
        cfg = config_manager.config
        with open(torrent_path, "rb") as f:
            torrent_b64 = base64.b64encode(f.read()).decode("ascii")
        # addTorrent 参数顺序：torrent, uris(文件 Web 种子，留空), options
        options = {"dir": save_dir or cfg.default_download_dir}
        gid = self.call("aria2.addTorrent", [torrent_b64, [], options])
        return gid

    @staticmethod
    def _parse_speed(speed: str) -> str:
        speed = speed.upper().strip()
        if speed.endswith("K"):
            return str(int(float(speed[:-1]) * 1024))
        if speed.endswith("M"):
            return str(int(float(speed[:-1]) * 1024 * 1024))
        if speed.endswith("G"):
            return str(int(float(speed[:-1]) * 1024 * 1024 * 1024))
        return speed

    @staticmethod
    def _benign(message: str, *keywords: str) -> bool:
        """判断 RPC 错误是否为无害情况（任务已暂停/已完成/已不存在等）"""
        lowered = message.lower()
        return any(k in lowered for k in keywords)

    def pause_task(self, gid: str) -> None:
        try:
            self.call("aria2.pause", [gid])
        except Aria2Error as e:
            # 幂等处理：任务已完成/已暂停/不存在时静默成功，避免重复点击报错
            if self._benign(str(e), "cannot be paused now", "is not found"):
                return
            raise

    def pause_all(self) -> None:
        self.call("aria2.pauseAll")

    def resume_task(self, gid: str) -> None:
        try:
            self.call("aria2.unpause", [gid])
        except Aria2Error as e:
            if self._benign(str(e), "cannot be unpaused now", "is not found"):
                return
            raise

    def resume_all(self) -> None:
        self.call("aria2.unpauseAll")

    def remove_task(self, gid: str) -> None:
        """删除任务：remove 处理活动/等待任务，removeDownloadResult 清除停止列表中的残留。

        两步都要做：remove 成功后任务结果仍留在停止列表里（removed 状态），
        必须再调 removeDownloadResult 才能彻底清除。
        remove 是异步落账：刚 remove 的任务可能短暂不在停止列表中，
        因此 removeDownloadResult 失败时短暂重试。
        """
        try:
            self.call("aria2.remove", [gid])
        except Aria2Error:
            pass
        last_err: Optional[Aria2Error] = None
        for _ in range(5):
            try:
                self.call("aria2.removeDownloadResult", [gid])
                return
            except Aria2Error as e:
                if self._benign(str(e), "is not found"):
                    return
                last_err = e
                time.sleep(0.3)
        if last_err:
            raise last_err

    def shutdown(self) -> bool:
        """优雅关闭 aria2c（触发会话保存）"""
        try:
            self.call("aria2.shutdown", retries=0, timeout=3.0)
            return True
        except Aria2Error:
            return False

    # ---------- 任务查询 ----------

    def _tell_all(self, method: str) -> List[dict]:
        """分页拉取 waiting/stopped 列表"""
        items: List[dict] = []
        offset = 0
        for _ in range(MAX_PAGES):
            result = self.call(method, [offset, PAGE_SIZE])
            batch = result or []
            items.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        return items

    def get_all_tasks(self) -> List[DownloadTask]:
        """获取全部任务"""
        active = self.call("aria2.tellActive") or []
        waiting = self._tell_all("aria2.tellWaiting")
        stopped = self._tell_all("aria2.tellStopped")
        return [self._parse_task(t) for t in [*active, *waiting, *stopped]]

    def get_global_stats(self) -> GlobalStats:
        result = self.call("aria2.getGlobalStat")
        return GlobalStats(
            download_speed=int(result.get("downloadSpeed", 0)),
            upload_speed=int(result.get("uploadSpeed", 0)),
            num_active=int(result.get("numActive", 0)),
            num_waiting=int(result.get("numWaiting", 0)),
            num_stopped=int(result.get("numStopped", 0)),
        )

    # ---------- 解析 ----------

    def _parse_task(self, data: Dict[str, Any]) -> DownloadTask:
        status_map = {
            "active": TaskStatus.ACTIVE,
            "waiting": TaskStatus.WAITING,
            "paused": TaskStatus.PAUSED,
            "error": TaskStatus.ERROR,
            "complete": TaskStatus.COMPLETE,
            "removed": TaskStatus.REMOVED,
        }
        status = status_map.get(data.get("status", ""), TaskStatus.ERROR)

        total_length = int(data.get("totalLength", 0))
        completed_length = int(data.get("completedLength", 0))
        progress = (completed_length / total_length * 100) if total_length > 0 else 0.0

        files = data.get("files", [])
        urls: List[str] = []
        filename: Optional[str] = None
        if files:
            uris = files[0].get("uris", [])
            urls = [u.get("uri", "") for u in uris if u.get("uri")]
            path = files[0].get("path", "")
            if path:
                filename = path.replace("\\", "/").split("/")[-1]

        # BT 任务名：元数据获取完成前 aria2 用 "[METADATA]<hash>" 占位，
        # 此时用创建时的磁力名称提示兜底；完成后用 bittorrent.info.name
        bittorrent = data.get("bittorrent") or {}
        bt_name = bittorrent.get("info", {}).get("name")
        # 磁力任务在元数据获取完成前没有 path/uris，用创建时的名称提示兜底
        gid = data.get("gid", "")
        if not urls and gid in self._name_hints:
            urls = [self._name_hints[gid]]

        def _is_metadata(name: Optional[str]) -> bool:
            return bool(name) and name.startswith("[METADATA]")

        display_name = bt_name if not _is_metadata(bt_name) else None
        if not display_name and filename and not _is_metadata(filename):
            display_name = filename
        if not display_name:
            display_name = self._name_hints.get(gid)

        # aria2 顶层 connections = 实际连接数（仅下载中的 HTTP 任务有值，
        # 停止任务与 BT 任务无意义；tellStatus 的 options 不回传 split 配置）
        actual_connections = int(data.get("connections", 0)) or None

        # BT 专属字段：做种人数 / 文件数 / 上传速度 / 已做种时长
        num_seeders = int(data.get("numSeeders", 0)) or None
        seeding_time = int(data.get("seedingTime", 0)) or None
        upload_speed = int(data.get("uploadSpeed", 0))

        return DownloadTask(
            gid=data.get("gid", ""),
            urls=urls,
            save_dir=data.get("dir", ""),
            filename=display_name,
            status=status,
            total_length=total_length,
            completed_length=completed_length,
            download_speed=int(data.get("downloadSpeed", 0)),
            connections=actual_connections,
            progress=round(progress, 2),
            is_bittorrent=bool(bittorrent),
            error_message=data.get("errorMessage") if status == TaskStatus.ERROR else None,
            num_seeders=num_seeders,
            num_files=len(files) if bittorrent and files else None,
            upload_speed=upload_speed,
            seeding_time=seeding_time,
        )


aria2_client = Aria2Client()
