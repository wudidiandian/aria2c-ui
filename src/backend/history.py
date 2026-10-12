import json
import logging
import threading
from pathlib import Path
from typing import List

from .models import DownloadTask, TaskStatus

logger = logging.getLogger(__name__)

# 历史记录上限，超出后丢弃最旧的
MAX_HISTORY = 500


class HistoryStore:
    """已完成/出错任务的本地持久化

    aria2 的 --save-session 不保存已完成任务，重启后任务会"消失"。
    本模块把 complete/error 任务落盘到 history.json，启动后与 aria2
    实时列表合并展示，实现跨重启可见。
    """

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._entries: dict = {}
        self._load()

    def _load(self):
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._entries = {d.get("gid", ""): d for d in data if isinstance(d, dict)}
        except Exception as e:
            logger.warning("读取任务历史失败（忽略）: %s", e)
            self._entries = {}

    def _save(self):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(list(self._entries.values()), f, ensure_ascii=False, indent=1)
        except Exception as e:
            logger.warning("写入任务历史失败: %s", e)

    def record(self, tasks: List[DownloadTask]):
        """把 complete/error 任务记入历史；removed 任务从历史中清除"""
        with self._lock:
            changed = False
            for t in tasks:
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
        """用户删除任务时同步移除历史记录"""
        with self._lock:
            if gid in self._entries:
                del self._entries[gid]
                self._save()

    def entries(self) -> List[dict]:
        with self._lock:
            return list(self._entries.values())
