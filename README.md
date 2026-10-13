<div align="center">

# Aria2c UI

基于 [aria2](https://github.com/aria2/aria2) 的轻量级 Windows 桌面下载器

*多线程 · 断点续传 · BT/磁力 · 便携免安装*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-blue)](https://github.com/wudidiandian/aria2c-ui/releases)
[![Python](https://img.shields.io/badge/python-3.10%2B-green.svg)](https://www.python.org/)
[![Release](https://img.shields.io/github/v/release/wudidiandian/aria2c-ui)](https://github.com/wudidiandian/aria2c-ui/releases)

[English](README.en.md) | 简体中文

</div>

---

Aria2c UI 是一个基于 [aria2c](https://github.com/aria2/aria2) 的桌面下载器：pywebview 窗口 + 原生 Web 前端 + 内置 aria2c 引擎。**单文件 18 MB，解压即用，界面完全离线，数据全部存放在用户目录。**

## 截图

![主界面](docs/screenshots/main.png)

| 新建任务 | 设置 |
|---|---|
| ![新建任务](docs/screenshots/task.png) | ![设置](docs/screenshots/settings.png) |

## 功能特性

- **HTTP(S) 下载**：多链接粘贴，每行一个独立任务；每任务可设连接数（-x）、分片数（-s）、限速
- **BT / 磁力链接**：支持 `magnet:?xt=urn:btih:...`，自动获取元数据并显示任务名
- **断点续传**：下载进度实时写入会话文件，重启软件/重启电脑后从断点继续
- **任务历史**：完成任务跨重启保留（aria2 不保存完成记录，本应用本地持久化）
- **实时进度**：后端状态推送，界面秒级刷新，无闪烁
- **任务管理**：暂停/继续/删除（含批量），按状态筛选，打开文件所在目录
- **全局设置**：并发任务数、默认连接/分片数、全局限速，保存立即生效
- **进程安全**：Job Object 内核级绑定，宿主进程无论怎么退出都不会残留 aria2c 孤儿进程；引擎意外崩溃自动重启
- **删除即彻底删除**：已删除任务永久清除（墓碑机制），重启不复活

## 安装

### 便携版（推荐）

1. 到 [Releases](https://github.com/wudidiandian/aria2c-ui/releases/latest) 下载 `Aria2cUI.exe`
2. 双击运行，无需安装

> 系统要求：Windows 10/11（需要 WebView2 Runtime，Win11 自带；Win10 若缺失首次启动会提示安装）

### 系统依赖

**无。** Python、aria2c、全部依赖库已打包进 exe 内，终端用户无需安装任何运行环境。

## 从源码运行

```bash
# 1. 安装依赖（Python 3.10+）
pip install -r requirements.txt

# 2. 下载 aria2c（如未包含在仓库中）
#    从 https://github.com/aria2/aria2/releases 下载 win-64bit 构建
#    将 aria2c.exe 放到 aria2c/ 目录

# 3. 开发运行
python build.py dev
```

## 打包

```bash
pip install -r requirements-dev.txt   # 含 PyInstaller

python build.py onefile   # 单文件版（推荐分发）
python build.py build     # 文件夹版（启动更快）
python build.py installer # Inno Setup 安装包（需预装 Inno Setup 6）

python build.py clean     # 清理构建产物
```

自定义图标：准备一张 1024x1024 透明背景 PNG 放到 `assets/icon-source.png`，运行 `python create_icon.py` 自动生成全套尺寸的 ico。

详见 [BUILD_GUIDE.md](BUILD_GUIDE.md)。

## 数据存储

所有用户数据保存在 `%APPDATA%\Aria2cUI`，与程序目录解耦：

```
%APPDATA%\Aria2cUI
├── aria2.session    # 未完成任务 + 断点续传位图（aria2 管理）
├── history.json     # 已完成/出错任务记录 + 已删除任务墓碑
├── config.json      # 设置
├── downloads/       # 默认下载目录
└── logs/            # 运行日志
```

删除 exe 不会删除数据；手动删除该目录即完全重置。把整个目录连同 `downloads/` 拷到新电脑，任务列表和断点全部保留。

## 架构

```
┌─────────────────────────────────────────┐
│           pywebview 窗口 (WebView2)      │
│  ┌───────────────────────────────────┐  │
│  │  前端 (HTML/CSS/原生 JS)            │
│  │  window.pywebview.api  ←→  Python  │  ← 唯一通信通道
│  └───────────────────────────────────┘  │
│  推送线程：轮询 aria2 → evaluate_js 推送   │
└───────────────┬─────────────────────────┘
                │ JSON-RPC (127.0.0.1)
┌───────────────▼─────────────────────────┐
│  aria2c 子进程（Job Object 绑定 + 优雅关闭）│
└─────────────────────────────────────────┘
```

- **单一通信通道**：前端通过 `pywebview js_api` 直接调用 Python 方法，无本地 HTTP 服务、无 CORS 暴露面
- **后端推送**：Python 侧轮询 aria2c RPC（空闲 2s / 有任务 1s），内容变化时通过 `evaluate_js` 推送
- **优雅关闭**：退出时先调 `aria2.shutdown` 保存会话；Job Object 保证宿主进程异常终止时引擎仍被系统回收
- **崩溃隔离**：aria2c 崩溃不影响界面，自动重启（上限 3 次）；下载中断开自动重连

### 项目结构

```
aria2c-ui/
├── aria2c/                 # aria2c 可执行文件（构建时打包，版本见 aria2c/VERSION.txt）
├── src/
│   ├── backend/            # Python 后端
│   │   ├── main.py         # 入口：pywebview 窗口 + js_api + 推送线程
│   │   ├── aria2_client.py # aria2 RPC 客户端（类型化错误、幂等操作）
│   │   ├── aria2_process.py# 进程管理（Job Object / 健康检查 / 自动重启）
│   │   ├── config.py       # 配置（%APPDATA%\Aria2cUI）
│   │   ├── history.py      # 任务历史 + 删除墓碑
│   │   └── models.py       # Pydantic 数据模型
│   └── frontend/           # Web 前端（零依赖、离线可用）
├── assets/                 # 图标源图与 ico
├── build.py                # 构建脚本
├── create_icon.py          # 图标生成（支持高清源图）
└── setup.iss               # Inno Setup 安装包脚本
```

## 路线图

- [x] Windows 单文件便携版
- [ ] Linux / macOS 支持（aria2c 换平台二进制，进程管理适配，架构已预留）
- [ ] BT 任务增强：种子文件、做种管理
- [ ] 浏览器接管下载（浏览器扩展）
- [ ] 多语言（i18n）
- [ ] 下载队列排序与批量编辑

平台说明：当前版本仅提供 Windows 构建。`aria2_client` / `history` / `config` 等模块本身是跨平台的，Linux/macOS 适配的主要工作在 `aria2_process` 的进程管理与引擎分发，欢迎 PR。

## 贡献

欢迎 Issue 和 PR！请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

本项目代码以 [MIT](LICENSE.txt) 许可证发布。

本项目捆绑分发了 [aria2](https://github.com/aria2/aria2)（GPL-2.0-or-later，含 OpenSSL 例外），其独立程序与本应用通过 JSON-RPC 进程间通信，不构成代码链接。aria2 及其他第三方组件的许可证详见 [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md)。

## 致谢

- [aria2](https://github.com/aria2/aria2) —— 强大的命令行下载引擎
- [pywebview](https://github.com/r0x0r/pywebview) —— 轻量桌面 WebView 容器
- 所有依赖库作者（见 THIRD-PARTY-LICENSES.md）
