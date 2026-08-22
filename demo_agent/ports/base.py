from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any


class ModelPort(ABC):
    @abstractmethod
    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        pass


class McpPort(ABC):
    @abstractmethod
    async def list_tools(self) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        pass


class KvCachePort(ABC):
    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        pass

    @abstractmethod
    async def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        pass


class DocumentParserPort(ABC):
    @abstractmethod
    async def parse(self, path: Path) -> str:
        pass


class OpenAiModelAdapter(ModelPort):
    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        raise NotImplementedError("OpenAI production adapter is not implemented")


class McpAdapter(McpPort):
    async def list_tools(self) -> list[dict[str, Any]]:
        raise NotImplementedError("MCP production adapter is not implemented")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        raise NotImplementedError("MCP production adapter is not implemented")


class KvCacheAdapter(KvCachePort):
    async def get(self, key: str) -> bytes | None:
        raise NotImplementedError("KV cache production adapter is not implemented")

    async def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        raise NotImplementedError("KV cache production adapter is not implemented")


class DocumentParserAdapter(DocumentParserPort):
    async def parse(self, path: Path) -> str:
        raise NotImplementedError("document parsing is not implemented")
