#!/usr/bin/env bash
# sidecar 打包骨架：python-build-standalone + uv 组装自包含运行时（TODO，阶段 D）。
#
# 目标产物：一个随应用分发的资源目录（独立可重定位 CPython + 站点包），
# 由 Rust 侧薄启动器拉起 `python -m demo_agent.server --stdio`，
# 不依赖系统 Python，规避 PyInstaller 对 pydantic / langchain 动态导入的冻结风险。
#
# 步骤（三平台 CI 矩阵各自执行）：
#   1) uv python install 3.13                       # 下载 python-build-standalone 发行版
#   2) uv venv --python 3.13 .sidecar/venv          # 独立 venv
#   3) uv pip install --python .sidecar/venv/bin/python -e .   # 安装运行时依赖
#   4) 精简 venv 后作为资源目录打包进 Tauri（bundle.resources）
#   5) 薄启动器：exec .sidecar/venv/bin/python -m demo_agent.server --stdio
set -euo pipefail

echo "TODO: 阶段 D 接入 python-build-standalone + uv 的 sidecar 打包流程（见脚本注释）"
