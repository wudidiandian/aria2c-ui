from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from datetime import datetime


class TaskStatus(str, Enum):
    ACTIVE = "active"           # 下载中
    WAITING = "waiting"         # 等待中
    PAUSED = "paused"           # 已暂停
    ERROR = "error"             # 出错
    COMPLETE = "complete"       # 已完成
    REMOVED = "removed"         # 已删除


class DownloadTaskCreate(BaseModel):
    """创建下载任务的请求模型"""
    urls: List[str] = Field(..., description="下载链接列表")
    save_dir: Optional[str] = Field(None, description="保存目录，None 使用默认目录")
    filename: Optional[str] = Field(None, description="自定义文件名")
    connections: int = Field(16, ge=1, le=16, description="每个服务器的最大连接数 (-x)")
    splits: int = Field(16, ge=1, le=16, description="下载分片数 (-s)")
    max_speed: Optional[str] = Field(None, description="单任务限速，如 '10M', '500K'")


class DownloadTask(BaseModel):
    """下载任务模型"""
    gid: str                                    # aria2 任务 ID
    urls: List[str]                             # 下载链接
    save_dir: str                               # 保存目录
    filename: Optional[str] = None              # 自定义文件名
    status: TaskStatus                          # 任务状态
    total_length: int = 0                       # 总大小（字节）
    completed_length: int = 0                   # 已完成大小（字节）
    download_speed: int = 0                     # 下载速度（字节/秒）
    connections: int = 16                       # 连接数
    splits: int = 16                            # 分片数
    progress: float = 0.0                       # 进度百分比
    error_message: Optional[str] = None         # 错误信息
    created_at: datetime                        # 创建时间
    completed_at: Optional[datetime] = None     # 完成时间


class GlobalStats(BaseModel):
    """全局统计信息"""
    download_speed: int = 0                     # 总下载速度
    upload_speed: int = 0                       # 总上传速度
    num_active: int = 0                         # 活动任务数
    num_waiting: int = 0                        # 等待任务数
    num_stopped: int = 0                        # 停止任务数


class AppConfig(BaseModel):
    """应用配置"""
    default_download_dir: str                   # 默认下载目录
    default_connections: int = 16               # 默认连接数
    default_splits: int = 16                    # 默认分片数
    max_concurrent_downloads: int = 5           # 最大同时下载数
    max_overall_download_limit: Optional[str] = None  # 全局限速
    aria2_rpc_port: int = 16800                 # RPC 端口
    aria2_rpc_secret: Optional[str] = None      # RPC 密钥