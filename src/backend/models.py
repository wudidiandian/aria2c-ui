from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class TaskStatus(str, Enum):
    ACTIVE = "active"           # 下载中
    WAITING = "waiting"         # 等待中
    PAUSED = "paused"           # 已暂停
    ERROR = "error"             # 出错
    COMPLETE = "complete"       # 已完成
    REMOVED = "removed"         # 已删除


class DownloadTaskCreate(BaseModel):
    """创建下载任务的请求模型（每个 URL 一个独立任务）"""
    urls: List[str] = Field(..., min_length=1, description="下载链接列表，每个链接一个任务")
    save_dir: Optional[str] = Field(None, description="保存目录，None 使用默认目录")
    filename: Optional[str] = Field(None, description="自定义文件名（仅单链接时有效）")
    connections: Optional[int] = Field(None, ge=1, le=16, description="每个服务器的最大连接数 (-x)，None 使用全局配置")
    splits: Optional[int] = Field(None, ge=1, le=16, description="下载分片数 (-s)，None 使用全局配置")
    max_speed: Optional[str] = Field(None, description="单任务限速，如 '10M', '500K'")


class DownloadTask(BaseModel):
    """下载任务模型"""
    gid: str                                    # aria2 任务 ID
    urls: List[str]                             # 下载链接
    save_dir: str                               # 保存目录
    filename: Optional[str] = None              # 文件名
    status: TaskStatus                          # 任务状态
    total_length: int = 0                       # 总大小（字节）
    completed_length: int = 0                   # 已完成大小（字节）
    download_speed: int = 0                     # 下载速度（字节/秒）
    connections: Optional[int] = None           # 实际连接数（仅下载中由 aria2 报告，其余为 None）
    progress: float = 0.0                       # 进度百分比
    is_bittorrent: bool = False                 # 是否为 BT/磁力任务
    error_message: Optional[str] = None         # 错误信息


class GlobalStats(BaseModel):
    """全局统计信息"""
    download_speed: int = 0                     # 总下载速度
    upload_speed: int = 0                       # 总上传速度
    num_active: int = 0                         # 活动任务数
    num_waiting: int = 0                        # 等待任务数
    num_stopped: int = 0                        # 停止任务数


class AppConfig(BaseModel):
    """应用配置（aria2_rpc_secret 仅保存在本地文件，不下发给前端）"""
    default_download_dir: str
    default_connections: int = Field(16, ge=1, le=16)
    default_splits: int = Field(16, ge=1, le=16)
    max_concurrent_downloads: int = Field(5, ge=1, le=20)
    max_overall_download_limit: Optional[str] = None
    aria2_rpc_port: int = 16800
    aria2_rpc_secret: Optional[str] = None
