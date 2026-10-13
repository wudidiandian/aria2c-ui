# 第三方组件许可证（THIRD-PARTY NOTICES）

> English summary at the bottom of this file.

本软件（Aria2c UI，含源码及其构建产物）捆绑或依赖以下第三方组件。
各组件归其原作者所有，本文件仅作摘要说明，具体效力以其原许可证文本为准。

---

## aria2

- 官网 / 源码：https://github.com/aria2/aria2
- 版本：**1.37.0**（官方 win-64bit-build1，2023-11-15 构建，见 `aria2c/VERSION.txt`）
- 许可证：**GPL-2.0-or-later**（含 OpenSSL 链接例外）
- 分发方式：以未修改的独立可执行文件 `aria2c.exe` 捆绑分发，与本应用
  通过 JSON-RPC（127.0.0.1 进程间通信）交互，不构成代码级链接
- aria2 官方构建附带的 OpenSSL 例外条款允许将 aria2 与 OpenSSL 库一同
  分发。aria2 的 GPL 许可证全文见：
  https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

> 若您基于本仓库重新分发包含 aria2c.exe 的安装包，请保留本说明文件，
> 或自行提供 aria2 对应版本源码的获取途径（官方 Releases 页即可满足）。

## Python 运行时

- 许可证：PSF License（https://docs.python.org/3/license.html）

## Python 依赖库

| 库 | 许可证 | 用途 |
|---|---|---|
| pywebview | BSD-3-Clause | 桌面 WebView 容器 |
| pydantic | MIT | 数据模型 |
| requests | Apache-2.0 | aria2 RPC HTTP 客户端 |
| psutil | BSD-3-Clause | 进程管理 |
| Pillow | MIT-CMU | 图标生成（仅构建期） |
| PyInstaller | GPL-2.0-or-later（含打包产物例外） | 打包（仅构建期；其许可证明确允许发布非 GPL 的打包产物） |
| Inno Setup | Inno Setup License | 安装包制作（仅构建期） |

## 字体与前端

前端为原生 HTML/CSS/JS，使用系统字体，无第三方运行时依赖。

---

如果本文件与各组件原始许可证文本存在冲突，以原始许可证为准。

---

## English Summary

This software (Aria2c UI, including its source code and build artifacts) bundles or
depends on the following third-party components. All components remain the property
of their respective owners; this file is a summary only — the original license texts
prevail.

- **aria2** v1.37.0 (official win-64bit-build1, see `aria2c/VERSION.txt`) — licensed under
  **GPL-2.0-or-later** (with an OpenSSL linking exception). Distributed as an unmodified
  standalone binary, communicating with this app as a separate process via JSON-RPC
  (mere aggregation, not code linking). Full GPL-2.0 text:
  https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
- Python runtime — PSF License
- pywebview (BSD-3-Clause), pydantic (MIT), requests (Apache-2.0), psutil (BSD-3-Clause)
- Build-time only: Pillow (MIT-CMU), PyInstaller (GPL-2.0-or-later with a bootloader
  exception permitting non-GPL bundled outputs), Inno Setup

Should this file conflict with any component's original license, the original license
applies.
