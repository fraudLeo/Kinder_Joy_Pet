"""日志系统：文件滚动日志 + 内存缓冲（供界面实时查看）。"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QPushButton, QLabel, QHBoxLayout

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "deskpet.log"


class ListHandler(logging.Handler):
    """在内存中保留最近 N 条格式化日志，供日志界面查看。"""

    def __init__(self, maxlen: int = 2000):
        super().__init__()
        self.records: list[str] = []
        self.maxlen = maxlen

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:  # noqa: BLE001 - 日志记录本身失败不应抛出
            return
        self.records.append(msg)
        if len(self.records) > self.maxlen:
            del self.records[: len(self.records) - self.maxlen]


_list_handler = ListHandler()


def setup_logging() -> None:
    """初始化根日志器：文件滚动 + 内存缓冲。重复调用安全。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    root = logging.getLogger()
    if root.handlers:  # 已初始化过
        return
    root.setLevel(logging.INFO)

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    _list_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(_list_handler)
    # 抑制 Qt 自身的噪音日志
    logging.getLogger("PyQt6").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def recent_logs(n: int = 500) -> list[str]:
    """返回最近的 n 条日志文本。"""
    return _list_handler.records[-n:]


class LogViewerDialog(QDialog):
    """实时日志查看器：每秒自动刷新，跟随底部；手动暂停或离开底部时暂停跟随。"""

    REFRESH_MS = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("日志查看器")
        self.resize(720, 460)
        self._follow = True  # 是否跟随底部刷新

        layout = QVBoxLayout(self)
        self.view = QPlainTextEdit(self)
        self.view.setReadOnly(True)
        self.view.setPlainText("\n".join(recent_logs()))
        layout.addWidget(self.view)

        self.pause_btn = QPushButton("暂停刷新", self)
        self.pause_btn.setCheckable(True)
        self.pause_btn.toggled.connect(self._on_pause_toggled)
        hint = QLabel("滚动离开底部会自动暂停，滚回底部恢复跟随", self)
        bar = QHBoxLayout()
        bar.addWidget(self.pause_btn)
        bar.addWidget(hint)
        bar.addStretch(1)
        layout.addLayout(bar)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(self.REFRESH_MS)

    def _on_pause_toggled(self, paused: bool) -> None:
        self._follow = not paused
        self.pause_btn.setText("继续刷新" if paused else "暂停刷新")
        if self._follow:
            self._refresh()

    def _refresh(self) -> None:
        if not self._follow:
            return
        sb = self.view.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 2
        if not at_bottom:
            # 用户在看历史：自动暂停，避免刷新打断
            self._follow = False
            self.pause_btn.setChecked(True)
            return
        self.view.setPlainText("\n".join(recent_logs()))
        sb.setValue(sb.maximum())

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)
