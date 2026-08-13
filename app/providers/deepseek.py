"""DeepSeek 余额查询：GET https://api.deepseek.com/user/balance"""
import requests

from . import BalanceInfo, BalanceProvider, register

API_URL = "https://api.deepseek.com/user/balance"


@register
class DeepSeekProvider(BalanceProvider):
    key = "deepseek"
    label = "DeepSeek"

    def fetch(self) -> BalanceInfo:
        resp = requests.get(
            API_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        infos = data.get("balance_infos") or []
        if not infos:
            return BalanceInfo(
                provider=self.key,
                label=self.label,
                error="响应中无余额数据",
                raw=resp.text[:200],
            )
        b = infos[0]
        total = float(b.get("total_balance") or 0.0)
        return BalanceInfo(
            provider=self.key,
            label=self.label,
            total=total,
            used=None,
            currency=str(b.get("currency", "")),
            raw=resp.text[:200],
        )
