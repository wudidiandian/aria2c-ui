import os
import json
from pathlib import Path
from typing import Optional
from .models import AppConfig


class ConfigManager:
    """配置管理器

    用户数据（配置/会话/日志/默认下载目录）统一放在 %APPDATA%/Aria2cUI，
    与程序目录解耦，避免打包后写入 _internal 或 Program Files 失败。
    程序资源（前端文件、aria2c.exe）仍按 __file__ 相对定位。
    """

    def __init__(self):
        # 程序资源根目录：源码运行 = 项目根；PyInstaller 运行 = _internal
        self.app_dir = Path(__file__).parent.parent.parent
        self.frontend_dir = Path(__file__).parent.parent / "frontend"

        # 用户数据目录
        appdata = os.getenv("APPDATA")
        self.data_dir = (Path(appdata) / "Aria2cUI") if appdata else self.app_dir / "data"
        self.config_file = self.data_dir / "config.json"
        self.session_file = self.data_dir / "aria2.session"
        self.log_dir = self.data_dir / "logs"
        self.downloads_dir = self.data_dir / "downloads"

        self.aria2c_dir = self.app_dir / "aria2c"
        self._config: Optional[AppConfig] = None

    # ---------- 配置读写 ----------

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def _load_config(self) -> AppConfig:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data = self._read_config_file(self.config_file)

        # 兼容旧版本：首次升级时从程序目录导入旧 config.json
        if data is None:
            legacy = self.app_dir / "config.json"
            if legacy.exists() and legacy.resolve() != self.config_file.resolve():
                data = self._read_config_file(legacy)

        if data is not None:
            try:
                # 忽略未知字段，缺失字段用默认值，避免旧配置导致崩溃
                config = AppConfig.model_validate(data)
            except Exception as e:
                print(f"解析配置失败: {e}，使用默认配置")
                config = self._default_config()
        else:
            config = self._default_config()

        self.save_config(config)
        return config

    def _read_config_file(self, path: Path) -> Optional[dict]:
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"读取配置失败 {path}: {e}")
            return None

    def _default_config(self) -> AppConfig:
        return AppConfig(
            default_download_dir=str(self.downloads_dir),
            default_connections=16,
            default_splits=16,
            max_concurrent_downloads=5,
            aria2_rpc_port=16800,
        )

    def save_config(self, config: AppConfig) -> bool:
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)
            self._config = config
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    def public_config(self) -> dict:
        """返回可下发给前端的安全配置（不含 RPC 密钥）"""
        c = self.config
        return {
            "default_download_dir": c.default_download_dir,
            "default_connections": c.default_connections,
            "default_splits": c.default_splits,
            "max_concurrent_downloads": c.max_concurrent_downloads,
            "max_overall_download_limit": c.max_overall_download_limit,
            "bt_seed_ratio": c.bt_seed_ratio,
            "bt_seed_time": c.bt_seed_time,
            "bt_listen_port": c.bt_listen_port,
            "bt_enable_dht": c.bt_enable_dht,
            "bt_trackers": c.bt_trackers,
        }

    # ---------- 路径 ----------

    def get_aria2c_path(self) -> str:
        aria2c_exe = self.aria2c_dir / "aria2c.exe"
        if aria2c_exe.exists():
            return str(aria2c_exe)
        return "aria2c"

    def ensure_downloads_dir(self) -> str:
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        return str(self.downloads_dir)

    def get_rpc_url(self) -> str:
        return f"http://127.0.0.1:{self.config.aria2_rpc_port}/jsonrpc"


config_manager = ConfigManager()
