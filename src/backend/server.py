import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import asyncio
from contextlib import asynccontextmanager

from .models import DownloadTask, DownloadTaskCreate, GlobalStats, AppConfig, TaskStatus
from .aria2_client import aria2_client
from .aria2_process import aria2_manager
from .config import config_manager


#  lifespan 上下文管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    print("正在启动 aria2c...")
    aria2c_started = False
    try:
        aria2c_started = aria2_manager.start()
        print("aria2c 启动成功")
        # 启动健康检查
        aria2_manager.start_health_check()
    except Exception as e:
        print(f"aria2c 启动失败: {e}")
        print("应用将继续运行，但下载功能可能不可用")
    
    yield
    
    # 关闭时
    print("正在关闭应用...")
    aria2_manager.stop_health_check()
    if aria2c_started:
        print("正在关闭 aria2c...")
        aria2_manager.stop()
    
    # 关闭异步客户端
    await aria2_client.close()


app = FastAPI(
    title="Aria2c UI",
    description="Aria2c 下载器 Web UI",
    version="1.0.0",
    lifespan=lifespan
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件目录
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")


# ============ API 路由 ============

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "aria2_running": aria2_manager.is_running()
    }


@app.get("/api/config", response_model=AppConfig)
async def get_config():
    """获取应用配置"""
    return config_manager.config


@app.post("/api/config")
async def update_config(config: AppConfig):
    """更新应用配置"""
    config_manager.save_config(config)
    return {"message": "配置已保存"}


@app.get("/api/tasks", response_model=List[DownloadTask])
async def get_tasks():
    """获取所有下载任务"""
    return await aria2_client.get_all_tasks()


@app.get("/api/tasks/active", response_model=List[DownloadTask])
async def get_active_tasks():
    """获取活动任务"""
    return await aria2_client.get_active_tasks()


@app.get("/api/tasks/waiting", response_model=List[DownloadTask])
async def get_waiting_tasks():
    """获取等待任务"""
    return await aria2_client.get_waiting_tasks()


@app.get("/api/tasks/stopped", response_model=List[DownloadTask])
async def get_stopped_tasks():
    """获取已停止任务"""
    return await aria2_client.get_stopped_tasks()


@app.post("/api/tasks")
async def create_task(task: DownloadTaskCreate):
    """创建下载任务"""
    # 确保保存目录存在
    if task.save_dir:
        os.makedirs(task.save_dir, exist_ok=True)
    else:
        task.save_dir = config_manager.ensure_downloads_dir()
    
    gid = await aria2_client.add_task(task)
    if gid:
        return {"gid": gid, "message": "任务创建成功"}
    else:
        raise HTTPException(status_code=500, detail="创建任务失败")


@app.post("/api/tasks/{gid}/pause")
async def pause_task(gid: str):
    """暂停任务"""
    if await aria2_client.pause_task(gid):
        return {"message": "任务已暂停"}
    else:
        raise HTTPException(status_code=500, detail="暂停任务失败")


@app.post("/api/tasks/{gid}/resume")
async def resume_task(gid: str):
    """继续任务"""
    if await aria2_client.resume_task(gid):
        return {"message": "任务已继续"}
    else:
        raise HTTPException(status_code=500, detail="继续任务失败")


@app.delete("/api/tasks/{gid}")
async def remove_task(gid: str):
    """删除任务"""
    if await aria2_client.remove_task(gid):
        return {"message": "任务已删除"}
    else:
        raise HTTPException(status_code=500, detail="删除任务失败")


@app.post("/api/tasks/pause-all")
async def pause_all_tasks():
    """暂停所有任务"""
    if await aria2_client.pause_all():
        return {"message": "所有任务已暂停"}
    else:
        raise HTTPException(status_code=500, detail="暂停任务失败")


@app.post("/api/tasks/resume-all")
async def resume_all_tasks():
    """继续所有任务"""
    if await aria2_client.resume_all():
        return {"message": "所有任务已继续"}
    else:
        raise HTTPException(status_code=500, detail="继续任务失败")


@app.get("/api/stats", response_model=GlobalStats)
async def get_global_stats():
    """获取全局统计"""
    return await aria2_client.get_global_stats()


@app.get("/api/version")
async def get_version():
    """获取 aria2 版本"""
    # 这里直接调用 _call 是异步的
    result = await aria2_client._call("aria2.getVersion")
    if result:
        return {
            "version": result.get("version"),
            "enabled_features": result.get("enabledFeatures", [])
        }
    else:
        raise HTTPException(status_code=500, detail="获取版本失败")


# ============ 静态文件服务 ============

# 检查前端目录是否存在
if os.path.exists(frontend_dir):
    # 挂载静态文件到 /static 路径
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    
    @app.get("/")
    async def root():
        """主页"""
        index_file = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "Aria2c UI 后端服务运行中"}
    
    @app.get("/{path:path}")
    async def catch_all(path: str):
        """捕获所有路由，返回 index.html（支持前端路由）"""
        # 排除 API 路径和静态文件路径
        if path.startswith("api/") or path.startswith("static/"):
            return {"message": "API 或静态文件路径"}
        index_file = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "Aria2c UI 后端服务运行中"}
else:
    @app.get("/")
    async def root():
        return {"message": "Aria2c UI 后端服务运行中，前端文件未找到"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
