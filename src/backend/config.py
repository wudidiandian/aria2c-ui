import os
import json
from pathlib import Path
from typing import Optional
from .models import AppConfig


class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.app_dir = Path(__file__).parent.parent.parent
        self.config_file = self.app_dir / "config.json"
        self.downloads_dir = self.app_dir / "downloads"
        self.aria2c_dir = self.app_dir / "aria2c"
        self._config: Optional[AppConfig] = None
        
    @property
    def config(self) -> AppConfig:
        """获取配置，首次调用时加载"""
        if self._config is None:
            self._config = self._load_config()
        return self._config
    
    def _load_config(self) -> AppConfig:
        """从文件加载配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return AppConfig(**data)
            except Exception as e:
                print(f"加载配置失败: {e}，使用默认配置")
        
        # 创建默认配置
        default_config = AppConfig(
            default_download_dir=str(self.downloads_dir),
            default_connections=16,
            default_splits=16,
            max_concurrent_downloads=5,
            aria2_rpc_port=16800
        )
        self.save_config(default_config)
        return default_config
    
    def save_config(self, config: AppConfig):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)
            self._config = config
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def get_aria2c_path(self) -> str:
        """获取 aria2c 可执行文件路径"""
        aria2c_exe = self.aria2c_dir / "aria2c.exe"
        if aria2c_exe.exists():
            return str(aria2c_exe)
        # 尝试从环境变量查找
        return "aria2c"
    
    def ensure_downloads_dir(self) -> str:
        """确保下载目录存在"""
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        return str(self.downloads_dir)
    
    def get_rpc_url(self) -> str:
        """获取 RPC 地址"""
        return f"http://localhost:{self.config.aria2_rpc_port}/jsonrpc"


# 全局配置实例
config_manager = ConfigManager()