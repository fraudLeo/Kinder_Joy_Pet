"""日志系统：文件滚动日志 + 内存缓冲（供界面实时查看）。"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtCore import QTimer, QStringListModel
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QListView

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


log = get_logger(__name__)


def recent_logs(n: int = 1000) -> list[str]:
    """返回最近的 n 条日志文本。"""
    return _list_handler.records[-n:]


class LogViewerDialog(QDialog):
    """实时日志查看器：每秒自动刷新，跟随底部；手动暂停或离开底部时暂停跟随。

    使用 QListView + QStringListModel（虚拟化渲染），避开 QPlainTextEdit 的
    QTextDocument 大文本路径（后者在部分 PyQt6 环境存在 fail-fast 崩溃问题）。
    """

    REFRESH_MS = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        log.info("日志窗口: __init__ 开始")
        self.setWindowTitle("日志查看器")
        self.resize(720, 460)
        self._follow = True   # 是否跟随底部刷新
        self._auto_paused = False  # 是否因查看历史而自动暂停（区别于手动暂停）
        self._shown = 0       # 已显示到界面的日志条数
        self._last_text = ""

        logs0 = recent_logs()
        log.info("日志窗口: 读取日志 %d 条", len(logs0))
        layout = QVBoxLayout(self)
        self.model = QStringListModel(self)
        self.view = QListView(self)
        self.view.setModel(self.model)
        self.view.setUniformItemSizes(True)  # 加速虚拟化渲染
        self._apply_logs(logs0)
        log.info("日志窗口: 模型填充完成（%d 行）", self.model.rowCount())
        # 打开后延迟滚到底部（等视图布局完成，scrollToBottom 内部处理时序）
        QTimer.singleShot(0, self.view.scrollToBottom)
        layout.addWidget(self.view)
        log.info("日志窗口: QListView 已挂载")

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
        # 补一次同步：把 __init__ 期间产生的日志（含本窗口的调试日志）纳入模型
        self._apply_logs(recent_logs())
        log.info("日志窗口: 定时器启动，初始化完成")

    def _apply_logs(self, logs: list[str]) -> None:
        """增量更新模型：新日志用 insertRow 追加，避免全量 setStringList 的模型重置。

        轮转截断/内容替换时（长度回退或末尾变化）才全量重建（低频）。
        """
        if len(logs) < self._shown or (len(logs) == self._shown and logs and logs[-1] != self._last_text):
            self.model.setStringList(logs)  # 轮转/替换场景（低频全量）
        elif len(logs) > self._shown:
            row = self.model.rowCount()
            self.model.insertRows(row, len(logs) - self._shown)
            for i, text in enumerate(logs[self._shown:]):
                self.model.setData(self.model.index(row + i), text)
        self._shown = len(logs)
        self._last_text = logs[-1] if logs else ""
        self.view.scrollToBottom()

    def _on_pause_toggled(self, paused: bool) -> None:
        if paused:
            self._follow = False
            self._auto_paused = False  # 手动暂停：滚回底部不自动恢复
        else:
            self._follow = True
            self._refresh()
        self.pause_btn.setText("继续刷新" if paused else "暂停刷新")

    def _refresh(self) -> None:
        try:
            self._do_refresh()
        except Exception:  # noqa: BLE001 - 渲染异常不应拖垮整个桌宠
            log.exception("日志刷新失败，暂停自动刷新")
            self._follow = False
            self._auto_paused = False
            self._timer.stop()
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText("刷新已暂停（异常）")

    def _do_refresh(self) -> None:
        sb = self.view.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 2
        if not self._follow:
            # 暂停中：若因查看历史自动暂停且已滚回底部，恢复跟随
            if self._auto_paused and at_bottom:
                self._follow = True
                self._auto_paused = False
                self.pause_btn.blockSignals(True)
                self.pause_btn.setChecked(False)
                self.pause_btn.setText("暂停刷新")
                self.pause_btn.blockSignals(False)
                self._do_refresh()
            return
        if not at_bottom:
            # 用户在看历史：自动暂停，避免刷新打断
            self._follow = False
            self._auto_paused = True
            self.pause_btn.blockSignals(True)
            self.pause_btn.setChecked(True)
            self.pause_btn.blockSignals(False)
            return
        # 虚拟化列表：内容变化时全量替换（只渲染可见行，开销小）
        logs = recent_logs()
        if len(logs) != self._shown or (logs and logs[-1] != self._last_text):
            self._apply_logs(logs)
        self.view.scrollToBottom()  # 跟随底部（内部处理布局时序）

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)
