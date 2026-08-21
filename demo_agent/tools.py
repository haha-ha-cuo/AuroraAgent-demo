"""工具集，作为 MCP 工具接入的占位。

真实实现中，MCP Server 暴露的工具经适配后可注册进能力特化层；
此处用只读 + 写工具演示工具调用闭环与确认门。
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool

_IGNORED_DIRS = {
    ".git",
    ".venv",
    ".uv-cache",
    ".pytest_cache",
    "site",
    "__pycache__",
    "node_modules",
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


DEFAULT_TOOLS = [list_files, read_file, write_file]
