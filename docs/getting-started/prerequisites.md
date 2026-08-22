# 环境准备

本项目的 Python 环境统一使用 [uv](https://docs.astral.sh/uv/) 管理。以下是第一阶段（文档站）所需的最小环境。

## 必备工具

| 工具 | 版本要求 | 用途 |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | 最新稳定版 | Python 环境与依赖管理 |
| [Git](https://git-scm.com/) | 2.x | 版本管理 |

### 安装 uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安装后确认版本：

```bash
uv --version
```

## Python 运行时

文档环境固定使用 **Python 3.13**（见根目录 `.python-version`）。首次运行 `uv sync` 时，uv 会自动下载并隔离所需的 Python 版本，无需手动安装。

## 桌面开发工具（构建桌面壳时需要）

仅开发/运行 Python 运行时无需以下工具；构建 `apps/desktop/` 桌面壳（Tauri + Nuxt）时需要：

- [Node.js](https://nodejs.org/)（前端构建，建议 LTS）
- [pnpm](https://pnpm.io/)（前端依赖管理）
- [Rust](https://rustup.rs/)（Tauri 核心；macOS 另需 Xcode Command Line Tools，Linux 需 webkit2gtk 等）

## 下一步

环境就绪后，参考[文档本地预览](docs-preview.md)在本地启动文档站。
