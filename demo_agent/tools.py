"""工具集，作为 MCP 工具接入的占位。

真实实现中，MCP Server 暴露的工具经适配后可注册进能力特化层；
此处用只读 + 写工具演示工具调用闭环与确认门。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from langchain_core.tools import tool

_IGNORED_DIRS = {
    ".git",
    ".venv",
    ".uv-cache",
    ".pytest_cache",
    ".pnpm-store",
    ".pnpm-cache",
    ".cargo-home",
    "site",
    "__pycache__",
    "node_modules",
    "target",
    ".nuxt",
    ".output",
    "dist",
}

# 敏感文件：工具层面拒绝列举/读取，避免密钥进入模型上下文（ADR-002）。
_SENSITIVE_EXACT = {".env", "id_rsa", "id_ed25519", "id_dsa", ".netrc"}
_SENSITIVE_SUBSTR = ("secret", "credential", "password", "api_key", "apikey")


def _is_sensitive(name: str) -> bool:
    n = name.lower()
    if n in _SENSITIVE_EXACT or (n.startswith(".env.") and n != ".env.example"):
        return True
    return any(k in n for k in _SENSITIVE_SUBSTR)


# 工具风险分级（ADR-005）：未知工具按 execute 处理，默认拒绝。
RISK_LEVELS: dict[str, str] = {
    "list_files": "read",
    "read_file": "read",
    "write_file": "write",
    "blender_create_sphere": "execute",
}
_DEFAULT_RISK = "execute"


def risk_of(tool_name: str) -> str:
    """返回工具的风险级别。"""
    return RISK_LEVELS.get(tool_name, _DEFAULT_RISK)


@tool
def list_files(path: str = ".") -> str:
    """列出指定目录（默认当前目录）下的文件，忽略构建产物目录。"""
    p = Path(path)
    if not p.exists():
        return f"路径不存在: {path}"
    if not p.is_dir():
        return f"不是目录: {path}"

    lines = [f"{path}"]
    for child in sorted(p.rglob("*")):
        if child.is_file() and not (_IGNORED_DIRS & set(child.parts)):
            if _is_sensitive(child.name):
                continue
            lines.append(str(child))
    return "\n".join(lines)


@tool
def read_file(path: str) -> str:
    """读取指定文本文件内容（只读）。"""
    p = Path(path)
    if not p.exists():
        return f"文件不存在: {path}"
    if not p.is_file():
        return f"不是文件: {path}"
    if _is_sensitive(p.name):
        return f"拒绝读取敏感文件: {path}"
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return f"读取失败: {exc}"


@tool
def write_file(path: str, content: str) -> str:
    """把内容写入指定文件（覆盖写）。属于写操作，需经确认门。"""
    p = Path(path)
    if _is_sensitive(p.name):
        return f"拒绝写入敏感文件: {path}"
    try:
        p.write_text(content, encoding="utf-8")
        return f"已写入: {path}"
    except Exception as exc:  # noqa: BLE001
        return f"写入失败: {exc}"


def _find_blender() -> str | None:
    """定位 Blender 可执行文件。"""
    explicit = os.environ.get("BLENDER_BIN")
    if explicit:
        return explicit
    found = shutil.which("blender")
    if found:
        return found
    candidate = "/Applications/Blender.app/Contents/MacOS/Blender"
    if Path(candidate).exists():
        return candidate
    return None


@tool
def blender_create_sphere(radius: float = 1.0, name: str = "Sphere") -> str:
    """在本地 Blender（headless）中创建一个球体。属于执行操作，需经确认门。"""
    blender_bin = _find_blender()
    if not blender_bin:
        return "未找到 Blender，请安装或设置 BLENDER_BIN。"

    safe_name = re.sub(r"[^A-Za-z0-9_]", "_", name) or "Sphere"
    script = (
        "import bpy\n"
        f"bpy.ops.mesh.primitive_uv_sphere_add(radius={radius!r})\n"
        "obj = bpy.context.active_object\n"
        f"obj.name = {safe_name!r}\n"
        "print('SPHERE_CREATED', obj.name, 'radius', " f"{radius!r})\n"
        "print('SCENE_OBJECTS', [o.name for o in bpy.data.objects])\n"
    )

    script_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(script)
            script_path = f.name
        proc = subprocess.run(
            [blender_bin, "--background", "--python", script_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "Blender 执行超时（>120s）。"
    except Exception as exc:  # noqa: BLE001
        return f"Blender 执行失败: {exc}"
    finally:
        if script_path:
            try:
                os.unlink(script_path)
            except OSError:
                pass

    out = (proc.stdout or "") + (proc.stderr or "")
    if "SPHERE_CREATED" in out:
        objects_line = next(
            (line for line in out.splitlines() if line.startswith("SCENE_OBJECTS")), ""
        )
        return f"成功创建球体（{safe_name}，半径 {radius}）。\n{objects_line}"
    return (
        f"Blender 执行未确认成功（exit={proc.returncode}）。\n"
        + "\n".join(out.splitlines()[-15:])
    )


DEFAULT_TOOLS = [list_files, read_file, write_file, blender_create_sphere]
