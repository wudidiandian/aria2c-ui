# Aria2c UI - Windows 下载器

基于 aria2c 的 Windows 图形界面下载器，支持多线程下载、任务管理等功能。

## 功能特性

- ✅ 新建下载任务（支持 HTTP/HTTPS，每个链接一个独立任务）
- ✅ 自定义下载目录
- ✅ 可设置下载连接数（-x 参数）和分片数（-s 参数）
- ✅ 开始/暂停/删除下载任务，支持批量操作
- ✅ 实时显示下载进度和速度（后端推送，无需轮询）
- ✅ 任务筛选（下载中/等待中/已暂停/已完成/出错）
- ✅ 打开文件所在目录
- ✅ 自动保存/恢复下载会话（程序关闭时优雅退出 aria2c）
- ✅ 内置 aria2c，无需单独安装
- ✅ 界面完全离线（无任何 CDN 依赖），便携免安装

## 架构说明

```
┌─────────────────────────────────────────┐
│           pywebview 窗口 (Edge Chromium)  │
│  ┌───────────────────────────────────┐  │
│  │  前端 (HTML/CSS/原生 JS)            │
│  │  window.pywebview.api  ←→  Python  │  ← 唯一通信通道
│  └───────────────────────────────────┘  │
│  推送线程：轮询 aria2 → evaluate_js 推送   │
└───────────────┬─────────────────────────┘
                │ JSON-RPC (127.0.0.1)
┌───────────────▼─────────────────────────┐
│  aria2c 子进程（RPC 优雅关闭，会话自动保存）  │
└─────────────────────────────────────────┘
```

- **单一通信通道**：前端通过 `pywebview js_api` 直接调用 Python 方法，无本地 HTTP 服务、无 CORS 暴露面
- **后端推送**：Python 侧轮询 aria2c RPC（空闲 2s/有任务 1s），内容变化时通过 `evaluate_js` 推送给前端
- **优雅关闭**：退出时先调用 `aria2.shutdown` RPC 让 aria2c 保存会话，超时才强制结束

## 项目结构

```
aria2c-ui/
├── aria2c/                 # aria2c 可执行文件
│   └── aria2c.exe         # 需要自行下载
├── src/
│   ├── backend/           # Python 后端
│   │   ├── main.py        # 程序入口（pywebview 窗口 + js_api + 推送线程）
│   │   ├── aria2_client.py    # aria2 RPC 客户端（同步、类型化错误）
│   │   ├── aria2_process.py   # aria2c 进程管理（启停/健康检查/自动重启）
│   │   ├── config.py      # 配置管理（%APPDATA%\Aria2cUI）
│   │   └── models.py      # 数据模型
│   └── frontend/          # Web 前端（零外部依赖）
│       ├── index.html     # 主页面
│       ├── css/style.css  # 样式（含深色模式）
│       └── js/app.js      # 前端逻辑
├── requirements.txt       # 运行依赖
├── requirements-dev.txt   # 构建/开发依赖
├── aria2c-ui.spec        # PyInstaller 配置
├── build.py              # 构建脚本
├── setup.iss             # Inno Setup 安装包脚本
└── README.md             # 本文件
```

用户数据（配置、会话、日志、默认下载目录）保存在 `%APPDATA%\Aria2cUI`，
与程序目录解耦，升级/重装不会丢失。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt        # 仅运行
pip install -r requirements-dev.txt    # 开发/打包（含 PyInstaller）
```

### 2. 下载 aria2c

1. 访问 https://github.com/aria2/aria2/releases
2. 下载 `aria2-1.37.0-win-64bit-build1.zip`
3. 解压并将 `aria2c.exe` 放到 `aria2c/` 目录

### 3. 开发运行

```bash
python build.py dev
```

### 4. 构建可执行文件

```bash
# 文件夹模式（推荐，启动更快）
python build.py build

# 单文件模式（更便携）
python build.py onefile
```

构建完成后，可执行文件位于 `dist/` 目录。

## 使用说明

### 新建下载任务

1. 点击"新建任务"按钮
2. 输入下载链接（支持多个链接，每行一个，**每个链接创建一个独立任务**）
3. 选择保存目录（可选，默认 `%APPDATA%\Aria2cUI\downloads`）
4. 设置下载参数：
   - **连接数 (-x)**: 每个服务器的最大连接数（1-16，默认 16）
   - **分片数 (-s)**: 下载分片数（1-16，默认 16）
   - **限速**: 单任务下载速度限制（可选）
5. 点击"创建任务"

### 任务管理

- **暂停/继续**: 点击任务卡片上的暂停/播放按钮
- **删除任务**: 点击任务卡片上的删除按钮
- **打开目录**: 点击文件夹图标直接打开文件所在目录
- **全部暂停/继续**: 使用工具栏上的批量操作按钮

### 设置

点击右上角的"设置"，可以修改：
- 默认下载目录
- 默认连接数和分片数
- 最大同时下载任务数（保存后立即同步到 aria2，无需重启）
- 全局下载限速

## 技术栈

- **桌面容器**: pywebview (Edge Chromium)
- **前后端通信**: pywebview js_api 桥（单通道）+ 后端状态推送
- **下载引擎**: aria2c（内置，JSON-RPC 控制）
- **前端**: 原生 HTML/CSS/JS（零依赖、离线可用）
- **打包工具**: PyInstaller + Inno Setup

## 注意事项

1. 首次运行时会在 `%APPDATA%\Aria2cUI` 下自动创建配置、会话文件和日志
2. 程序会自动管理 aria2c 进程（意外退出会自动重启，最多 3 次）
3. 关闭程序时通过 RPC 优雅退出 aria2c，会话自动保存，下次启动可继续下载
4. 如果 16800 端口被占用，请修改 `%APPDATA%\Aria2cUI\config.json` 中的 `aria2_rpc_port`
5. 如需配置 RPC 密钥，同样编辑 `config.json` 中的 `aria2_rpc_secret`（不会出现在日志中）

## 许可证

MIT License


## 编译构建
在编译构建前要安装好 Inno Setup
下载并安装：[](https://jrsoftware.org/isdl.php)<https://jrsoftware.org/isdl.php> ，下载完默认安装就好了
现在选取了 innosetup-6.7.1.exe 进行安装

## 执行编译构建  
conda activate fileopt

python build.py installer

python build.py clean      # 清理
