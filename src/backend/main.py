import os
import sys
import threading
import time
import asyncio
import webview
import uvicorn
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.backend.server import app
from src.backend.aria2_process import aria2_manager
from src.backend.config import config_manager


class Api:
    """暴露给前端 JavaScript 调用的 API"""
    
    def select_directory(self, default_path=""):
        """打开目录选择对话框"""
        result = webview.windows[0].create_file_dialog(
            webview.FOLDER_DIALOG,
            directory=default_path or config_manager.config.default_download_dir
        )
        if result and len(result) > 0:
            return result[0]
        return None
    
    def select_save_directory(self):
        """选择保存目录（用于新建任务）"""
        return self.select_directory(config_manager.config.default_download_dir)
    
    def select_default_directory(self):
        """选择默认下载目录（用于设置）"""
        return self.select_directory(config_manager.config.default_download_dir)
    
    def get_version(self):
        """获取应用版本"""
        # 由于这里是在 pywebview 线程中同步调用，
        # 我们不得不创建一个临时的事件循环或使用同步方式。
        # 考虑到这是不常调用的方法，我们可以使用同步方式或者简单返回。
        return {
            "app_version": "1.0.0",
            "aria2_version": "unknown"  # 简化，避免复杂的异步等待
        }


def start_server():
    """在后台线程启动 FastAPI 服务器"""
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="warning")


def main():
    """主函数"""
    # 确保工作目录正确
    os.chdir(project_root)
    
    # 启动后端服务器
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # 等待服务器启动
    time.sleep(2)
    
    # 创建 API 实例
    api = Api()
    
    # 窗口配置
    window_title = "Aria2c 下载器"
    window_width = 1200
    window_height = 800
    
    # 创建窗口
    webview.create_window(
        title=window_title,
        url="http://127.0.0.1:8080",
        width=window_width,
        height=window_height,
        min_size=(800, 600),
        resizable=True,
        fullscreen=False,
        text_select=True,
        confirm_close=True,
        js_api=api
    )
    
    # 启动 webview
    webview.start(
        debug=False,  # 生产环境设为 False
        http_server=False,  # 我们使用自己的 FastAPI 服务器
        gui="edgechromium"  # Windows 使用 Edge Chromium 引擎
    )
    
    # 清理
    print("正在关闭应用...")
    # 注意：这里不能简单调用 stop，可能需要发信号给 server 线程或 aria2c
    aria2_manager.stop()


if __name__ == "__main__":
    main()
