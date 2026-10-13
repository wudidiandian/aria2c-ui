# 贡献指南

感谢关注 Aria2c UI！欢迎提交 Issue 与 Pull Request。

## 开发环境

```bash
# Windows 10/11，Python 3.10+
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt

# 下载 aria2c（如仓库未含）
# https://github.com/aria2/aria2/releases → aria2c.exe 放入 aria2c/

.venv\Scripts\python build.py dev    # 开发运行
```

## 项目结构速览

- `src/backend/main.py` —— 程序入口：pywebview 窗口、js_api（前端唯一调用入口）、状态推送线程
- `src/backend/aria2_client.py` —— aria2 RPC 客户端；错误用 `Aria2Error`/`Aria2Unavailable` 类型化表达
- `src/backend/aria2_process.py` —— aria2c 进程生命周期（**平台相关层**）
- `src/backend/history.py` / `config.py` —— 用户数据持久化（**平台无关**）
- `src/frontend/` —— 零依赖原生前端，键控更新避免列表闪烁

## 提交规范

- 一个 PR 聚焦一件事；提交信息用中文或英文均可，说明"为什么"
- 改动后请实际运行验证（`python build.py dev`），涉及进程管理/会话的改动请在真机上验证重启场景
- 不引入需要联网的前端依赖（保持离线可用）；不新增 HTTP 服务

## 想适配 Linux / macOS？

欢迎！当前平台相关的部分集中在：

1. `aria2_process.py` —— Job Object（Windows 特有）需要替换为对应平台的进程组管理
2. 引擎分发 —— Linux/macOS 需要用户自装 aria2 或下载对应平台二进制
3. 打包流程 —— PyInstaller onedir + 平台图标格式

建议先开 Issue 讨论方案再动手。
