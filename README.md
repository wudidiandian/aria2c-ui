# Aria2c UI - Windows 下载器

基于 aria2c 的 Windows 图形界面下载器，支持多线程下载、任务管理等功能。

## 功能特性

- ✅ 新建下载任务（支持 HTTP/HTTPS）
- ✅ 自定义下载目录
- ✅ 可设置下载线程数（-x 参数）和分片数（-s 参数）
- ✅ 开始/暂停/删除下载任务
- ✅ 实时显示下载进度和速度
- ✅ 深色/浅色主题切换
- ✅ 内置 aria2c，无需单独安装
- ✅ 单文件可执行程序，便携免安装

## 项目结构

```
aria2c-ui/
├── aria2c/                 # aria2c 可执行文件
│   └── aria2c.exe         # 需要自行下载
├── src/
│   ├── backend/           # Python 后端
│   │   ├── main.py        # 程序入口（pywebview）
│   │   ├── server.py      # FastAPI 服务
│   │   ├── aria2_client.py    # aria2 RPC 客户端
│   │   ├── aria2_process.py   # aria2c 进程管理
│   │   ├── config.py      # 配置管理
│   │   └── models.py      # 数据模型
│   └── frontend/          # Web 前端
│       ├── index.html     # 主页面
│       └── js/
│           └── app.js     # 前端逻辑
├── downloads/             # 默认下载目录
├── requirements.txt       # Python 依赖
├── aria2c-ui.spec        # PyInstaller 配置
├── build.py              # 构建脚本
└── README.md             # 本文件
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
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
2. 输入下载链接（支持多个链接，每行一个）
3. 选择保存目录（可选，默认使用程序目录下的 downloads 文件夹）
4. 设置下载参数：
   - **连接数 (-x)**: 每个服务器的最大连接数（1-32，默认 16）
   - **分片数 (-s)**: 下载分片数（1-32，默认 16）
   - **限速**: 单任务下载速度限制（可选）
5. 点击"开始下载"

### 任务管理

- **暂停/继续**: 点击任务卡片上的暂停/播放按钮
- **删除任务**: 点击任务卡片上的删除按钮
- **全部暂停/开始**: 使用工具栏上的批量操作按钮

### 设置

点击右上角的设置图标，可以修改：
- 默认下载目录
- 默认连接数和分片数
- 最大同时下载任务数

## 技术栈

- **后端**: Python + FastAPI + Uvicorn
- **前端**: HTML5 + TailwindCSS + Alpine.js
- **桌面容器**: pywebview (Edge Chromium)
- **打包工具**: PyInstaller

## 注意事项

1. 首次运行时会自动创建 `config.json` 配置文件和 `downloads` 下载目录
2. 程序会自动管理 aria2c 进程，无需手动启动
3. 关闭程序时会自动保存 aria2c 会话，下次启动可继续下载
4. 如果 16800 端口被占用，请修改 `config.json` 中的 `aria2_rpc_port`

## 许可证

MIT License