# 更新日志 (Changelog)

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.1.0] - 2026-10-12

### 架构重构

- 通信架构从「pywebview 壳 + FastAPI 本地 HTTP」重构为 **pywebview js_api 单通道**，
  移除本地 HTTP 服务与 CORS 暴露面
- 下载状态由后端推送线程统一推送（空闲 2s / 活跃 1s），前端不再轮询
- 错误链路类型化（`Aria2Error` / `Aria2Unavailable`），错误原因直达界面提示

### 新增

- BT / 磁力链接下载支持（自动元数据获取与任务命名）
- 任务历史持久化：已完成任务跨重启保留
- 删除墓碑机制：已删除任务（含出错任务）重启后不再复活
- aria2c 进程 Job Object 绑定：宿主进程异常退出时由内核回收引擎，无孤儿进程
- 引擎意外崩溃自动重启（上限 3 次）
- 日志系统：写入 `%APPDATA%\Aria2cUI\logs\app.log`
- 应用图标（支持高清源图自动生成多尺寸 ico）

### 修复

- 分片数/连接数启动参数硬编码，改为读取配置
- 任务卡片显示伪造的"连接/分片"数值，改为 aria2 实际连接数
- tellStatus options 为空导致的假数据展示
- 完成任务重启后消失（本地历史合并）
- 出错任务无法彻底删除（会话残留复活）
- 删除任务后停止列表残留
- 空状态遮罩在存在任务时仍然显示（CSS `[hidden]` 被覆盖）
- 图标从 16px 基底放大导致的模糊
- 构建：PyInstaller 解释器自动探测、打包体积优化（38 MB → 18 MB）

### 安全

- 移除本地 HTTP 服务，无网络端口暴露
- RPC 密钥不再下发前端、不再写入日志

## [1.0.0] - 2025

- 初始版本：HTTP 多任务下载、任务管理、实时进度、深色模式

[1.1.0]: https://github.com/wudidiandian/aria2c-ui/releases/tag/v1.1.0
[1.0.0]: https://github.com/wudidiandian/aria2c-ui/releases/tag/v1.0.0
