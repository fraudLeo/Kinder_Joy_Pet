"""提醒调度：相对时间解析、定时/重复提醒、番茄钟、健康提醒。

所有提醒到期后通过 triggered 信号发出，由外部（气泡等）展示。
"""
import re
import time
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .logger import get_logger

log = get_logger(__name__)


def parse_relative(text: str) -> int | None:
    """解析相对时间表达式，返回秒数。支持「3分钟后」「5分钟」「2小时」「30秒」等。

    数字与单位之间允许空格与「之/后/钟」等噪声字。
    """
    text = text.strip().lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(分钟|小时|秒|min|hour|hr|sec|minute|h|m|s)", text)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2)
    if unit in ("秒", "sec", "s"):
        return int(num)
    if unit in ("分钟", "min", "minute", "m"):
        return int(num * 60)
    if unit in ("小时", "hour", "hr", "h"):
        return int(num * 3600)
    return None


@dataclass
class Reminder:
    title: str
    message: str
    due: float  # 触发时间戳（epoch 秒）
    interval: int = 0  # 0=一次性；>0=每 interval 秒重复


class ReminderManager(QObject):
    """提醒调度器：每秒检查到期提醒，触发信号，处理重复。"""

    triggered = pyqtSignal(str, str)  # (标题, 消息)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.reminders: list[Reminder] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check)
        self._timer.start(1000)

    def add(self, title: str, message: str, delay_seconds: int, interval: int = 0) -> Reminder:
        r = Reminder(title, message, time.time() + delay_seconds, interval)
        self.reminders.append(r)
        log.info("新增提醒 [%s] 延迟 %s 秒 重复 %s", title, delay_seconds, interval)
        return r

    def remove_by_title(self, title: str) -> None:
        self.reminders = [r for r in self.reminders if r.title != title]

    def _check(self) -> None:
        now = time.time()
        for r in list(self.reminders):
            if now >= r.due:
                self.triggered.emit(r.title, r.message)
                if r.interval > 0:
                    r.due += r.interval  # 下次触发
                else:
                    self.reminders.remove(r)


class Pomodoro(QObject):
    """番茄钟：25 分钟专注 + 5 分钟休息，可暂停/恢复/取消。"""

    WORK_SEC = 25 * 60
    BREAK_SEC = 5 * 60

    status_changed = pyqtSignal(str)  # 状态文本（阶段 + 倒计时）
    finished = pyqtSignal(str, str)  # 阶段结束 (标题, 消息)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._remaining = self.WORK_SEC
        self._phase = "专注"
        self._running = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._emit_status()

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if not self._running:
            self._running = True
            log.info("番茄钟开始：%s", self._phase)
            self._emit_status()

    def pause(self) -> None:
        if self._running:
            self._running = False
            log.info("番茄钟暂停")
            self._emit_status()

    def toggle(self) -> None:
        if self._running:
            self.pause()
        else:
            self.start()

    def cancel(self) -> None:
        self._running = False
        self._remaining = self.WORK_SEC
        self._phase = "专注"
        log.info("番茄钟取消")
        self._emit_status()

    def _tick(self) -> None:
        if not self._running:
            return
        self._remaining -= 1
        if self._remaining <= 0:
            if self._phase == "专注":
                self.finished.emit("番茄钟", "专注结束，休息 5 分钟吧 🍅")
                self._phase = "休息"
                self._remaining = self.BREAK_SEC
            else:
                self.finished.emit("番茄钟", "休息结束，开始新一轮专注 💪")
                self._phase = "专注"
                self._remaining = self.WORK_SEC
        self._emit_status()

    def _emit_status(self) -> None:
        mm, ss = divmod(max(self._remaining, 0), 60)
        state = "运行中" if self._running else "已暂停"
        self.status_changed.emit(f"{self._phase} {mm:02d}:{ss:02d}（{state}）")

    def status_text(self) -> str:
        mm, ss = divmod(max(self._remaining, 0), 60)
        state = "运行中" if self._running else "已暂停"
        return f"{self._phase} {mm:02d}:{ss:02d}（{state}）"

    def menu_text(self) -> str:
        """托盘信息区文本：未开始 / 专注中 08:25 / 休息中 03:10。"""
        if not self._running and self._remaining == self.WORK_SEC and self._phase == "专注":
            return "未开始"
        mm, ss = divmod(max(self._remaining, 0), 60)
        phase = "专注中" if self._phase == "专注" else "休息中"
        return f"{phase} {mm:02d}:{ss:02d}"


class HealthReminders(QObject):
    """健康提醒：喝水/休息眼睛/站起来，按固定间隔重复。"""

    triggered = pyqtSignal(str, str)

    PRESETS = {
        "喝水": (60 * 45, "该喝水啦 💧"),
        "休息眼睛": (60 * 60, "眼睛休息一下，看看远处 👀"),
        "站起来活动": (60 * 90, "起来活动活动，久坐伤身 🧍"),
    }

    def __init__(self, manager: ReminderManager, parent: QObject | None = None):
        super().__init__(parent)
        self._manager = manager
        self._enabled: dict[str, Reminder] = {}

    def toggle(self, name: str, enabled: bool) -> None:
        if name not in self.PRESETS:
            return
        if enabled and name not in self._enabled:
            interval, msg = self.PRESETS[name]
            self._enabled[name] = self._manager.add(name, msg, interval, interval)
            log.info("开启健康提醒：%s", name)
        elif not enabled and name in self._enabled:
            self._manager.reminders.remove(self._enabled.pop(name))
            log.info("关闭健康提醒：%s", name)

    def is_enabled(self, name: str) -> bool:
        return name in self._enabled

    def remaining_text(self, name: str) -> str | None:
        """已开启提醒的剩余时间（mm:ss），未开启返回 None。"""
        r = self._enabled.get(name)
        if r is None:
            return None
        secs = max(int(r.due - time.time()), 0)
        mm, ss = divmod(secs, 60)
        return f"{mm:02d}:{ss:02d}"
