import json
import logging
import threading
import time
from pathlib import Path
from typing import List, Set

from .models import DownloadTask, TaskStatus

logger = logging.getLogger(__name__)

# 历史记录上限，超出后丢弃最旧的
MAX_HISTORY = 500
# 已删除 gid 墓碑上限（防止无限增长）
MAX_DELETED = 1000


class HistoryStore:
    """已完成/出错任务的本地持久化 + 已删除任务墓碑

    两个问题在这里解决：
    1. aria2 的 --save-session 不保存已完成任务，重启后任务会"消失"，
       所以把 complete/error 任务落盘，启动后与 aria2 实时列表合并展示。
    2. 出错任务会被 --save-session 写进会话文件，界面上删除后重启又
       被恢复。删除时把 gid 记入墓碑并持久化，启动后自动清除会话里
       恢复出来的残留任务。
    """

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._entries: dict = {}
        self._deleted: dict = {}  # gid -> 删除时间戳（保持插入序）
        self._load()

    def _load(self):
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                # 旧格式（纯任务列表）
                self._entries = {d.get("gid", ""): d for d in data if isinstance(d, dict)}
            elif isinstance(data, dict):
                self._entries = data.get("tasks", {}) or {}
                self._deleted = data.get("deleted", {}) or {}
        except Exception as e:
            logger.warning("读取任务历史失败（忽略）: %s", e)
            self._entries = {}

    def _save(self):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({"tasks": self._entries, "deleted": self._deleted}, f, ensure_ascii=False, indent=1)
        except Exception as e:
            logger.warning("写入任务历史失败: %s", e)

    def record(self, tasks: List[DownloadTask]):
        """把 complete/error 任务记入历史；removed 任务从历史中清除"""
        with self._lock:
            changed = False
            for t in tasks:
                if t.gid in self._deleted:
                    continue  # 墓碑任务不入历史、不再展示
                if t.status in (TaskStatus.COMPLETE, TaskStatus.ERROR):
                    data = t.model_dump()
                    if self._entries.get(t.gid) != data:
                        self._entries[t.gid] = data
                        changed = True
                elif t.status == TaskStatus.REMOVED and t.gid in self._entries:
                    del self._entries[t.gid]
                    changed = True

            # 超限裁剪最旧的（保持插入顺序，字典已按插入序）
            if len(self._entries) > MAX_HISTORY:
                for gid in list(self._entries.keys())[: len(self._entries) - MAX_HISTORY]:
                    del self._entries[gid]

            if changed:
                self._save()

    def remove(self, gid: str):
        """用户删除任务：移出历史并记入墓碑（重启后也不复活）"""
        with self._lock:
            if gid not in self._deleted:
                self._deleted[gid] = time.time()
                if len(self._deleted) > MAX_DELETED:
                    for old in list(self._deleted.keys())[: len(self._deleted) - MAX_DELETED]:
                        del self._deleted[old]
            if gid in self._entries:
                del self._entries[gid]
            self._save()

    def deleted_gids(self) -> Set[str]:
        with self._lock:
            return set(self._deleted.keys())

    def entries(self) -> List[dict]:
        with self._lock:
            return list(self._entries.values())
