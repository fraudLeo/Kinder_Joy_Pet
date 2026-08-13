"""OpenRouter 额度查询：GET https://openrouter.ai/api/v1/key"""
import requests

from . import BalanceInfo, BalanceProvider, register

API_URL = "https://openrouter.ai/api/v1/key"


@register
class OpenRouterProvider(BalanceProvider):
    key = "openrouter"
    label = "OpenRouter"

    def fetch(self) -> BalanceInfo:
        resp = requests.get(
            API_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        limit = data.get("limit")
        usage = data.get("usage")
        if limit is None:
            return BalanceInfo(
                provider=self.key,
                label=self.label,
                error="响应中无额度数据",
                raw=resp.text[:200],
            )
        return BalanceInfo(
            provider=self.key,
            label=self.label,
            total=float(limit),
            used=float(usage or 0.0),
            currency="USD",
            raw=resp.text[:200],
        )
