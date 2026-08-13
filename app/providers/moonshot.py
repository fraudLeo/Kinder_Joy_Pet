"""Kimi (Moonshot) 余额查询：GET https://api.moonshot.cn/v1/users/me/balance

该接口只返回可用余额，无"总额"概念，因此把可用余额记在 total 上。
"""
import requests

from . import BalanceInfo, BalanceProvider, register

API_URL = "https://api.moonshot.cn/v1/users/me/balance"


@register
class MoonshotProvider(BalanceProvider):
    key = "moonshot"
    label = "Kimi/Moonshot"

    def fetch(self) -> BalanceInfo:
        resp = requests.get(
            API_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        available = data.get("available_balance")
        if available is None:
            return BalanceInfo(
                provider=self.key,
                label=self.label,
                error="响应中无余额数据",
                raw=resp.text[:200],
            )
        return BalanceInfo(
            provider=self.key,
            label=self.label,
            total=float(available),
            used=None,
            currency="CNY",
            raw=resp.text[:200],
        )
