"""Token 余量厂商插件：基类、余额数据结构与注册表。

新增厂商只需继承 BalanceProvider 并用 @register 注册到 REGISTRY。
"""
from dataclasses import dataclass


@dataclass
class BalanceInfo:
    """一次余额查询的标准化结果。total 与 used 均为金额（各厂商货币可能不同）。

    - total: 总余额（无"总额"概念的厂商把剩余额填在 total，used 为 None）
    - used:  已使用金额；无此概念时留 None
    """

    provider: str = ""
    label: str = ""
    total: float | None = None
    used: float | None = None
    currency: str = ""
    error: str | None = None
    raw: str = ""

    @property
    def remaining(self) -> float | None:
        if self.total is None:
            return None
        return max(self.total - (self.used or 0.0), 0.0)

    @property
    def percent(self) -> float | None:
        """剩余百分比（0-100）；无法计算时返回 None。"""
        if self.total is None or self.total <= 0:
            return None
        rem = self.remaining
        return (rem / self.total * 100.0) if rem is not None else None

    def summary(self) -> str:
        if self.error:
            return f"{self.label}: 查询失败 - {self.error}"
        rem = self.remaining
        if rem is None:
            return f"{self.label}: 无数据"
        pct = self.percent
        if pct is not None:
            return f"{self.label}: 余 {rem:.2f}{self.currency} ({pct:.1f}%)"
        return f"{self.label}: 余 {rem:.2f}{self.currency}"


class BalanceProvider:
    """余额查询插件基类。"""

    key: str = "base"
    label: str = "Base"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch(self) -> BalanceInfo:
        raise NotImplementedError


REGISTRY: dict[str, type[BalanceProvider]] = {}


def register(cls: type[BalanceProvider]) -> type[BalanceProvider]:
    """把厂商插件注册进 REGISTRY（key -> 类）。"""
    REGISTRY[cls.key] = cls
    return cls
