"""微信消息源：统一抽象 + 模拟源（演示）+ WeChatFerry 接入骨架。

MessageSource 子类负责把消息通过 message_received 信号发出：
    {"sender": "联系人名", "content": "消息内容"}

真实接入（WcferrySource）需要：
    pip install wcferry
    并安装官方支持列表内的微信 3.9.x 版本，详见 wcferry 文档。
"""
import random

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .logger import get_logger

log = get_logger(__name__)


class MessageSource(QObject):
    """消息源基类。"""

    message_received = pyqtSignal(dict)  # {"sender": str, "content": str}

    def start(self) -> None:  # pragma: no cover - 抽象方法
        raise NotImplementedError

    def stop(self) -> None:  # pragma: no cover - 抽象方法
        raise NotImplementedError


class DummySource(MessageSource):
    """模拟消息源：定时随机产生联系人消息，用于演示气泡效果。"""

    SENDERS = ["张三", "李四", "产品群", "女朋友", "老板", "文件传输助手"]
    CONTENTS = [
        "在吗？",
        "这个方案明天上午给我，辛苦了",
        "吃饭了吗",
        "哈哈哈笑死",
        "代码记得提交",
        "周末有空吗，出来聚聚",
        "帮忙看下这个 bug，线上报错了",
        "收到，谢谢！",
        "会议改到下午三点",
        "文档我发你邮箱了",
        "新需求：加个导出按钮",
        "早点休息，别熬太晚",
    ]

    def __init__(self, parent: QObject | None = None, min_interval: int = 2000, max_interval: int = 5000):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._send_one)
        self._min, self._max = min_interval, max_interval
        self._last_interval: int | None = None

    def start(self) -> None:
        log.info("模拟消息源启动")
        self._schedule_next()

    def stop(self) -> None:
        log.info("模拟消息源停止")
        self._timer.stop()

    def _schedule_next(self) -> None:
        self._last_interval = random.randint(self._min, self._max)
        self._timer.start(self._last_interval)

    def _send_one(self) -> None:
        msg = {
            "sender": random.choice(self.SENDERS),
            "content": random.choice(self.CONTENTS),
        }
        self.message_received.emit(msg)
        self._schedule_next()


class WcferrySource(MessageSource):
    """WeChatFerry 真实消息源（骨架）。

    使用前需要: pip install wcferry，并运行指定版本的微信。
    消息格式映射：文本消息取 msg.content；其他类型暂忽略（可扩展）。
    """

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._wcf = None
        self._started = False

    def start(self) -> None:
        try:
            import wcferry  # noqa: F401
        except ImportError:
            log.error(
                "未安装 wcferry（pip install wcferry），且需要微信 3.9.x 指定版本，"
                "详见 https://github.com/lich0821/WeChatFerry"
            )
            self.message_received.emit(
                {"sender": "系统", "content": "wcferry 未安装，无法监控微信"}
            )
            return
        # TODO: 按 wcferry 官方示例初始化 wcf，注册消息回调并映射为 dict 后 emit。
        # 示例（版本相关，以官方文档为准）：
        #   self._wcf = wcferry.Wcf()
        #   self._wcf.enable_receiving_msg()
        #   self._wcf.on_message = self._on_raw
        #   self._started = True
        raise NotImplementedError("WcferrySource 待按 wcferry 文档接入")

    def stop(self) -> None:
        if self._wcf is not None and self._started:
            # self._wcf.disable_receiving_msg()
            pass
        self._started = False
