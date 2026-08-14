"""Token 余量监控：后台线程轮询各厂商余额，阈值预警（带去重），提供状态文本。

所有请求在 QThreadPool 中执行，不阻塞 UI 线程。
"""
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal

from .logger import get_logger
from .providers import REGISTRY, BalanceInfo, BalanceProvider

log = get_logger(__name__)


class _FetchTask(QRunnable):
    """在后台线程执行一次余额查询。"""

    def __init__(
        self,
        provider_cls: type[BalanceProvider],
        api_key: str,
        done_cb: callable,
        key: str,
    ):
        super().__init__()
        self.provider_cls = provider_cls
        self.api_key = api_key
        self.done_cb = done_cb
        self.key = key

    def run(self) -> None:
        try:
            info = self.provider_cls(self.api_key).fetch()
        except Exception as exc:  # noqa: BLE001 - 网络错误统一转成 BalanceInfo
            info = BalanceInfo(
                provider=self.key,
                label=getattr(self.provider_cls, "label", self.key),
                error=f"{type(exc).__name__}: {exc}",
            )
        self.done_cb(self.key, info)


class TokenMonitor(QObject):
    """余额轮询调度器。配置中的 providers: {厂商key: {api_key, ...}}。"""

    status_changed = pyqtSignal()          # 状态文本更新后触发
    warn = pyqtSignal(str, str)            # (标题, 消息) 预警信号

    def __init__(self, config: dict, parent: QObject | None = None):
        super().__init__(parent)
        self.config = config
        self.results: dict[str, BalanceInfo] = {}
        self._warned: set[str] = set()
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(3)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.check_all)
        interval = int(config.get("token_check_interval_sec", 300))
        self._timer.start(max(interval, 30) * 1000)

    # ---------- 对外接口 ----------
    def start(self) -> None:
        """立即查询一次，之后按配置间隔轮询。"""
        log.info("Token 监控启动，轮询间隔 %s 秒", self.config.get("token_check_interval_sec", 300))
        self.check_all()

    def stop(self) -> None:
        self._timer.stop()
        self._pool.clear()

    def check_all(self) -> None:
        for key, cfg in (self.config.get("providers") or {}).items():
            provider_cls = REGISTRY.get(key)
            if provider_cls is None:
                log.warning("未注册的厂商: %s（可用: %s）", key, ", ".join(REGISTRY))
                continue
            api_key = (cfg or {}).get("api_key") or ""
            if not api_key:
                log.warning("厂商 %s 未配置 api_key，跳过", key)
                continue
            self._pool.start(_FetchTask(provider_cls, api_key, self._on_result, key))

    def status_text(self) -> str:
        lines = []
        for key in sorted(self.results):
            lines.append(self.results[key].summary())
        if lines:
            return "\n".join(lines)
        # 已配置厂商但尚无查询结果（如刚填 Key / 轮询未到）→ 提示查询中
        configured = [
            k for k, cfg in (self.config.get("providers") or {}).items()
            if (cfg or {}).get("api_key")
        ]
        if configured:
            return "正在查询余额…（刚配置的 Key 已触发查询，请稍候）"
        return "未配置 Token 厂商（设置中填写 API Key）"

    def menu_text(self) -> str:
        """托盘信息区文本：API Token 余额：{数值}；无数据显示 --。"""
        for key in sorted(self.results):
            info = self.results[key]
            if not info.error and info.remaining is not None:
                return f"API Token 余额：{info.remaining:.2f}{info.currency}"
        return "API Token 余额：--"

    # ---------- 内部 ----------
    def _on_result(self, key: str, info: BalanceInfo) -> None:
        self.results[key] = info
        self._evaluate(key, info)
        self.status_changed.emit()

    def _evaluate(self, key: str, info: BalanceInfo) -> None:
        """阈值预警，带去重：低余额只提醒一次，恢复后重置。"""
        if info.error:
            log.warning("%s 查询失败: %s", info.label, info.error)
            self._warned.discard(key)
            return
        pct = info.percent
        threshold = float(self.config.get("token_warn_percent", 20))
        if pct is None:
            log.info("%s 无百分比可算（余 %s%s）", info.label, info.remaining, info.currency)
            return
        if pct < threshold:
            if key not in self._warned:
                self._warned.add(key)
                msg = (
                    f"{info.label} 余量仅剩 {pct:.1f}%"
                    f"（{info.remaining:.2f}{info.currency}），请及时充值！"
                )
                log.warning(msg)
                self.warn.emit("Token 余量预警", msg)
        else:
            self._warned.discard(key)
