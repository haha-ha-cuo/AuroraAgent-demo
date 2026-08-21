"""本地 API 管理：统一管理模型密钥与端点，构建模型客户端。

设计要点：
- 密钥只从环境变量 / .env 读取，绝不写入图状态、日志或输出；
- 无密钥时回退 mock 模式（确定性输出，便于离线演示与测试）；
- 适配任意 OpenAI 兼容端点（OpenAI / DeepSeek / 本地网关）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel

# 在导入期加载 .env（若存在），幂等。
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """模型接入配置。"""

    api_key: str | None
    base_url: str
    model: str

    @property
    def mode(self) -> str:
        return "live" if self.api_key else "mock"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_key=os.getenv("AGENT_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("AGENT_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("AGENT_MODEL", "gpt-4o-mini"),
        )

    def redacted(self) -> dict[str, Any]:
        """用于日志展示的脱敏摘要——绝不包含密钥明文。"""
        return {
            "mode": self.mode,
            "model": self.model,
            "base_url": self.base_url,
            "api_key": "***" if self.api_key else None,
        }

    def build_model(self) -> BaseChatModel | None:
        """构建模型客户端；无密钥时返回 None（mock 模式）。"""
        if not self.api_key:
            return None
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
        )
