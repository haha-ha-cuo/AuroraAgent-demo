"""能力特化层：可插拔地注入上下文、工具与提示。

与缓存解耦（见文档 ADR-001）。用户通过 with_* 方法注册自定义能力，
注入内容只影响 Agent 可见的上下文与工具，不侵入委派图结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.tools import BaseTool


@dataclass
class CapabilityRegistry:
    """能力特化注册表。

    用法::

        registry = (
            CapabilityRegistry(name="my-team")
            .with_context("团队编码规范：...")
            .with_tool(my_tool)
            .with_prompt("review", "评审时关注以下清单：...")
        )
    """

    name: str = "default"
    system_context: list[str] = field(default_factory=list)
    tools: list[BaseTool] = field(default_factory=list)
    extra_prompts: dict[str, str] = field(default_factory=dict)

    def with_context(self, text: str) -> "CapabilityRegistry":
        """注入一段上下文。"""
        self.system_context.append(text)
        return self

    def with_tool(self, tool: BaseTool) -> "CapabilityRegistry":
        """注册一个工具（可含 MCP 工具）。"""
        self.tools.append(tool)
        return self

    def with_prompt(self, key: str, text: str) -> "CapabilityRegistry":
        """注入一段命名提示（如评审清单）。"""
        self.extra_prompts[key] = text
        return self

    def system_prompt(self) -> str:
        """把已注册能力组装成子 Agent 的系统提示。"""
        parts = [f"你是「{self.name}」团队中的一名子 Agent。"]
        parts.extend(self.system_context)
        for key, text in self.extra_prompts.items():
            parts.append(f"[{key}] {text}")
        parts.append("只使用提供的工具，客观地完成任务并返回简洁结果。")
        return "\n".join(parts)
