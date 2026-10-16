import json
import logging
import os
import sys
import time
import atexit
import base64
import threading
from pathlib import Path

# 支持直接以脚本运行（python src/backend/main.py）
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import webview

from src.backend.aria2_client import aria2_client, Aria2Error
from src.backend.aria2_process import aria2_manager
from src.backend.config import config_manager
from src.backend.history import HistoryStore
from src.backend.models import AppConfig, DownloadTaskCreate, DownloadTask

APP_VERSION = "1.2.0"
APP_TITLE = "Aria2c 下载器"

logger = logging.getLogger("aria2c-ui")


class _Aria2StartState:
    """aria2 启动握手：让 init() 等到首次启动尝试结束，避免首帧误报"未连接\""""

    def __init__(self):
        self.done = threading.Event()
        self.error = None


aria2_start_state = _Aria2StartState()

# 任务历史：aria2 会话不保存已完成任务，用本地文件补齐跨重启可见性
history_store = HistoryStore(config_manager.data_dir / "history.json")


def collect_tasks():
    """合并 aria2 实时任务与本地历史（complete/error），并同步历史落盘"""
    tasks = aria2_client.get_all_tasks()

    # 用户已删除的任务（墓碑）：aria2 会话恢复出来的残留，静默清除且不再展示
    deleted = history_store.deleted_gids()
    if deleted:
        for t in [t for t in tasks if t.gid in deleted]:
            try:
                aria2_client.remove_task(t.gid)
            except Aria2Error:
                pass
        tasks = [t for t in tasks if t.gid not in deleted]

    history_store.record(tasks)
    live_gids = {t.gid for t in tasks}
    history_tasks = [
        DownloadTask(**d) for d in history_store.entries() if d.get("gid") not in live_gids
    ]
    return tasks + history_tasks


def setup_logging():
    """日志写入 %APPDATA%/Aria2cUI/logs/app.log，开发模式同时输出到控制台"""
    config_manager.log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    file_handler = logging.FileHandler(config_manager.log_dir / "app.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    if sys.stdout is not None:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(fmt)
        root.addHandler(console)


def safe_save_dir(path: str) -> str:
    """校验保存目录：必须是合法的本地绝对路径"""
    path = (path or "").strip()
    if not path:
        return config_manager.ensure_downloads_dir()
    if not os.path.isabs(path):
        raise ValueError("保存目录必须是绝对路径")
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    return path


class Api:
    """暴露给前端 window.pywebview.api 的唯一通信通道"""

    # ---- 状态 ----

    def init(self):
        return self._snapshot(with_version=True)

    def refresh(self):
        return self._snapshot(with_version=False)

    def _snapshot(self, with_version: bool) -> dict:
        # 等待首次启动尝试结束（最多 3 秒），避免启动窗口期误报"未连接"
        aria2_start_state.done.wait(3)

        payload = {
            "config": config_manager.public_config(),
            "tasks": [],
            "stats": {
                "download_speed": 0, "upload_speed": 0,
                "num_active": 0, "num_waiting": 0, "num_stopped": 0,
            },
            "aria2": {
                "ok": False,
                "error": aria2_start_state.error,
                "starting": not aria2_start_state.done.is_set(),
            },
        }
        if with_version:
            payload["app_version"] = APP_VERSION
        try:
            payload["tasks"] = [t.model_dump() for t in collect_tasks()]
            payload["stats"] = aria2_client.get_global_stats().model_dump()
            payload["aria2"] = {"ok": True, "error": None, "starting": False}
        except Aria2Error as e:
            payload["aria2"] = {"ok": False, "error": str(e), "starting": False}
        return payload

    # ---- 任务操作 ----

    def create_task(self, payload: dict):
        task = DownloadTaskCreate(**payload)
        save_dir = safe_save_dir(task.save_dir)
        if save_dir != task.save_dir:
            task.save_dir = save_dir
        gids = aria2_client.add_task(task)
        return {"gids": gids, "count": len(gids), "message": f"已创建 {len(gids)} 个任务"}

    def pause_task(self, gid: str):
        aria2_client.pause_task(gid)
        return {"message": "任务已暂停"}

    def resume_task(self, gid: str):
        aria2_client.resume_task(gid)
        return {"message": "任务已继续"}

    def remove_task(self, gid: str):
        aria2_client.remove_task(gid)
        history_store.remove(gid)
        return {"message": "任务已删除"}

    def pause_all(self):
        aria2_client.pause_all()
        return {"message": "所有任务已暂停"}

    def resume_all(self):
        aria2_client.resume_all()
        return {"message": "所有任务已继续"}

    # ---- BT / 种子文件 ----

    def select_torrent_file(self):
        """打开原生文件选择框选取 .torrent 种子文件"""
        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("种子文件 (*.torrent)", "所有文件 (*.*)"),
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def create_torrent_task(self, payload: dict):
        """从 .torrent 种子文件创建 BT 任务（含做种参数）"""
        path = (payload.get("path") or "").strip()
        if not path:
            raise ValueError("未选择种子文件")
        if Path(path).suffix.lower() != ".torrent":
            raise ValueError("请选择 .torrent 种子文件")

        torrent_path = Path(path)
        if not torrent_path.is_file():
            raise ValueError(f"文件不存在: {path}")
        # 合理大小限制（种子文件通常 < 10MB），防止误选大文件
        size = torrent_path.stat().st_size
        if size > 10 * 1024 * 1024:
            raise ValueError("种子文件超过 10MB，疑似选择错误")
        with open(torrent_path, "rb") as f:
            head = f.read(1)
        if head != b"d":
            raise ValueError("不是有效的种子文件（bencode 格式校验失败）")

        save_dir = safe_save_dir(payload.get("save_dir"))
        gid = aria2_client.add_torrent(path, save_dir)
        return {"gids": [gid], "count": 1, "message": "BT 任务已创建"}

    # ---- 配置 ----

    def save_config(self, payload: dict):
        current = config_manager.config
        data = current.model_dump()

        # 只接受前端允许修改的字段，端口/密钥等敏感项不可通过前端篡改
        allowed = {
            "default_download_dir", "default_connections", "default_splits",
            "max_concurrent_downloads", "max_overall_download_limit",
            "bt_seed_ratio", "bt_seed_time", "bt_listen_port",
            "bt_enable_dht", "bt_trackers",
        }
        for key in allowed & set(payload.keys()):
            data[key] = payload[key]

        updated = AppConfig(**data)
        if not config_manager.save_config(updated):
            raise ValueError("配置写入失败，请检查 %APPDATA%/Aria2cUI 目录权限")

        # 立即同步可热更新的选项到 aria2
        hot_updated = False
        if aria2_manager.is_running():
            try:
                options = {
                    "max-concurrent-downloads": str(updated.max_concurrent_downloads),
                    # BT 做种选项支持热更新（按任务对新建/后续任务生效）
                    "seed-ratio": str(updated.bt_seed_ratio),
                    "seed-time": str(updated.bt_seed_time),
                }
                if updated.max_overall_download_limit:
                    options["max-overall-download-limit"] = updated.max_overall_download_limit
                if updated.bt_trackers is not None:
                    trackers = ",".join(
                        t.strip() for t in updated.bt_trackers.splitlines() if t.strip()
                    )
                    options["bt-tracker"] = trackers
                aria2_client.change_global_option(options)
                hot_updated = True
            except Aria2Error as e:
                return {"message": f"配置已保存，但同步到 aria2 失败: {e}"}
        note = "" if hot_updated else "（BT 选项将在重启应用后生效）"
        return {"message": f"配置已保存{note}"}

    # ---- 原生对话框 / 系统集成 ----

    def select_directory(self, kind: str = "new_task"):
        default = config_manager.config.default_download_dir
        result = webview.windows[0].create_file_dialog(
            webview.FOLDER_DIALOG, directory=default or str(config_manager.downloads_dir)
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def open_folder(self, path: str):
        if not os.path.isdir(path):
            raise ValueError(f"目录不存在: {path}")
        os.startfile(path)  # noqa 仅 Windows
        return {"message": "已打开目录"}

    def get_app_version(self):
        return {"app_version": APP_VERSION}


def push_loop(window):
    """后端推送线程：轮询 aria2 并将变化推给前端（含 aria2 启动）"""
    # 启动 aria2c（GUI 已显示，失败也继续运行，前端会显示离线状态）
    try:
        aria2_manager.start()
    except Exception as e:
        logger.error("aria2c 启动失败: %s", e)
        aria2_start_state.error = str(e)
    finally:
        aria2_start_state.done.set()

    last_signature = None
    while True:
        payload = {
            "tasks": [],
            "stats": {
                "download_speed": 0, "upload_speed": 0,
                "num_active": 0, "num_waiting": 0, "num_stopped": 0,
            },
            "aria2": {"ok": False, "error": None, "starting": False},
        }
        try:
            tasks = collect_tasks()
            stats = aria2_client.get_global_stats()
            payload["tasks"] = [t.model_dump() for t in tasks]
            payload["stats"] = stats.model_dump()
            payload["aria2"] = {"ok": True, "error": None, "starting": False}
            interval = 1 if stats.num_active else 2
        except Exception as e:
            payload["aria2"] = {"ok": False, "error": str(e), "starting": False}
            interval = 2

        # 内容无变化则跳过推送，降低 evaluate_js 开销
        signature = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        if signature != last_signature:
            last_signature = signature
            try:
                window.evaluate_js(
                    f"window.__push && window.__push({json.dumps(payload, ensure_ascii=False, default=str)})"
                )
            except Exception as e:
                logger.debug("推送失败（窗口可能已关闭）: %s", e)

        time.sleep(interval)


def on_closed():
    """窗口关闭后的清理：优雅停止 aria2c（保存会话）"""
    logger.info("应用关闭，正在停止 aria2c...")
    aria2_manager.stop()
    aria2_client.close()


def main():
    setup_logging()

    # 兜底清理：无论何种退出路径（正常关闭 / Ctrl+C / 异常），都尝试优雅停止 aria2c。
    # 极端情况（进程被硬杀）由 aria2c 所在的 Job Object 兜底回收。
    atexit.register(on_closed)

    frontend_index = config_manager.frontend_dir / "index.html"
    if not frontend_index.exists():
        raise FileNotFoundError(f"前端文件不存在: {frontend_index}")

    window = webview.create_window(
        title=APP_TITLE,
        url=str(frontend_index),
        width=1200,
        height=800,
        min_size=(860, 560),
        js_api=Api(),
        text_select=True,
        confirm_close=True,
    )
    window.events.closed += on_closed

    try:
        webview.start(
            func=push_loop,
            args=(window,),
            debug=False,
            http_server=True,   # 由 pywebview 内置服务器托管前端（本地静态资源）
            gui="edgechromium",
        )
    finally:
        on_closed()


if __name__ == "__main__":
    main()
