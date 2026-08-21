"""敏感操作确认门（ADR-005 最小实现）。

风险分级：read（读，默认放行）/ write（写，需确认）/ execute（执行，需确认）。
未知风险按 execute 处理——最小权限原则，默认拒绝。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

Risk = str  # "read" | "write" | "execute"
ConfirmFn = Callable[[str, str], bool]  # (action, risk) -> 是否允许


@dataclass
class ConfirmationGate:
    """确认门。

    - ``confirm``：确认回调；None 时写/执行按 ``default_allow`` 决定。
    - ``auto_allow_read``：读操作自动放行。
    - ``default_allow``：无确认回调时，写/执行的默认结果（默认拒绝）。
    """

    confirm: ConfirmFn | None = None
    auto_allow_read: bool = True
    default_allow: bool = False

    def request(self, action: str, risk: Risk) -> bool:
        """返回该操作是否被允许。"""
        if risk == "read" and self.auto_allow_read:
            return True
        if self.confirm is not None:
            return bool(self.confirm(action, risk))
        return self.default_allow


def interactive_confirm(action: str, risk: str) -> bool:
    """交互式确认（stdin 提示）。"""
    answer = input(f"⚠ 需要确认 [{risk}]：{action}\n允许？[y/N] ").strip().lower()
    return answer in ("y", "yes")


def yes_confirm(action: str, risk: str) -> bool:
    """无条件放行（--yes）。"""
    return True


def deny_confirm(action: str, risk: str) -> bool:
    """无条件拒绝（安全默认）。"""
    return False
