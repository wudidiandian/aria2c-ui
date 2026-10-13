# Aria2c UI 构建指南

本文档介绍如何将 Aria2c UI 打包成 Windows 可执行文件和安装包。

## 环境要求

- Windows 10/11
- Python 3.10+
- Inno Setup 6（用于创建安装包，仅 `installer` 命令需要）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 创建应用程序图标（可选）

```bash
python create_icon.py
```

默认生成程序内置图标。如需自定义：准备一张 1024x1024 透明背景 PNG 放到
`assets/icon-source.png`，再次运行会自动从高清源图生成全套尺寸（16-256）的
`assets/icon.ico`。

### 3. 构建可执行文件

#### 方式一：文件夹模式（推荐）
```bash
python build.py build
```

输出：`dist/Aria2cUI/` 文件夹

#### 方式二：单文件模式
```bash
python build.py onefile
```

输出：`dist/Aria2cUI.exe` 单个文件

### 4. 构建 Windows 安装包

```bash
python build.py installer
```

输出：`installer/Aria2cUI-1.0.0-Setup.exe`

## 详细说明

### 构建流程

`build.py installer` 命令会执行以下步骤：

1. **清理** - 删除旧的构建文件
2. **安装依赖** - 确保所有 Python 包已安装
3. **构建 EXE** - 使用 PyInstaller 打包
4. **创建图标** - 生成应用程序图标（如果不存在）
5. **编译安装包** - 使用 Inno Setup 创建安装程序

### 安装包特性

- ✓ 中文安装界面
- ✓ 桌面快捷方式（可选）
- ✓ 开始菜单快捷方式
- ✓ 自动卸载程序
- ✓ 清理下载文件和配置

### 文件说明

| 文件 | 说明 |
|------|------|
| `build.py` | 主构建脚本 |
| `setup.iss` | Inno Setup 脚本 |
| `aria2c-ui.spec` | PyInstaller 配置 |
| `create_icon.py` | 图标生成工具 |
| `LICENSE.txt` | 许可证文件 |

## 常见问题

### Q: 提示 "未找到 Inno Setup"

**解决：** 下载并安装 Inno Setup：
- 官网：https://jrsoftware.org/isdl.php
- 下载 `innosetup-6.x.x.exe` 并安装

### Q: 提示 "aria2c.exe 不存在"

**解决：** 手动下载 aria2c：
1. 访问 https://github.com/aria2/aria2/releases
2. 下载 `aria2-1.37.0-win-64bit-build1.zip`
3. 解压并将 `aria2c.exe` 放到 `aria2c/` 目录

### Q: 构建失败

**尝试：**
```bash
python build.py clean
python build.py installer
```

## 发布检查清单

- [ ] 版本号已更新（`setup.iss` 和 `build.py`）
- [ ] 图标已创建
- [ ] aria2c.exe 已包含
- [ ] 安装包测试通过
- [ ] 卸载功能测试通过

## 命令参考

```bash
# 开发运行
python build.py dev

# 仅构建 EXE（文件夹模式）
python build.py build

# 构建单文件 EXE
python build.py onefile

# 构建安装包
python build.py installer

# 清理构建文件
python build.py clean