"""桌宠主窗口：透明置顶、GIF/占位动画、鼠标拖拽、右键菜单与系统托盘。

功能入口通过 callbacks 注入，避免与具体业务模块强耦合。
"""
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QAction, QColor, QIcon, QMovie, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QMenu, QSystemTrayIcon, QWidget

from .logger import get_logger

log = get_logger(__name__)


def _make_tray_icon() -> QIcon:
    """程序化生成一个圆形小图标，避免依赖外部素材。"""
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 200, 87))
    p.drawEllipse(4, 4, 56, 56)
    p.setBrush(QColor(60, 40, 20))
    p.drawEllipse(16, 22, 10, 12)
    p.drawEllipse(38, 22, 10, 12)
    p.end()
    return QIcon(pix)


class DesktopPet(QWidget):
    def __init__(self, config: dict, callbacks: dict | None = None):
        super().__init__()
        self.config = config
        self.callbacks = callbacks or {}
        self._drag_offset: QPoint | None = None
        self._frame = 0
        self._menu: QMenu | None = None

        self._build_window()
        self._load_animation()
        self._build_tray()

    # ---------- 窗口 ----------
    def _build_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("桌宠")

        size = int(self.config.get("pet_size", 200))
        self.setFixedSize(size, size)
        self.label = QLabel(self)
        self.label.setGeometry(0, 0, size, size)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # ---------- 动画 ----------
    def _load_animation(self) -> None:
        gif = self.config.get("gif_path")
        if gif and Path(gif).exists():
            self.movie = QMovie(gif)
            self.movie.setCacheMode(QMovie.CacheMode.CacheAll)
            self.label.setMovie(self.movie)
            self.movie.start()
            log.info("加载 GIF 动画: %s", gif)
        else:
            self.movie = None
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._draw_placeholder)
            self._timer.start(700)
            self._draw_placeholder()
            if gif:
                log.warning("指定的 GIF 不存在，使用内置占位动画: %s", gif)
            else:
                log.info("未配置 GIF，使用内置占位动画")

    def _draw_placeholder(self) -> None:
        """绘制一个简单像素脸，帧间眨眼，保证无素材也能看到桌宠在动。"""
        size = self.width()
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        m = size / 200.0  # 以 200px 为基准缩放
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 200, 87))
        p.drawEllipse(int(16 * m), int(20 * m), int(168 * m), int(160 * m))

        blink = self._frame % 4 == 3  # 每 4 帧眨一次眼
        p.setBrush(QColor(60, 40, 20))
        if blink:
            p.drawRoundedRect(int(40 * m), int(72 * m), int(44 * m), int(8 * m), 4, 4)
            p.drawRoundedRect(int(116 * m), int(72 * m), int(44 * m), int(8 * m), 4, 4)
        else:
            p.drawEllipse(int(42 * m), int(62 * m), int(22 * m), int(26 * m))
            p.drawEllipse(int(118 * m), int(62 * m), int(22 * m), int(26 * m))

        p.setBrush(QColor(240, 140, 140))
        p.drawEllipse(int(80 * m), int(118 * m), int(40 * m), int(22 * m))
        p.end()

        self.label.setPixmap(pix)
        self._frame += 1

    # ---------- 拖拽 ----------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        event.accept()

    def moveEvent(self, event) -> None:
        """桌宠移动时通知外部（如气泡队列跟随）。"""
        super().moveEvent(event)
        fn = self.callbacks.get("on_moved")
        if fn is not None:
            fn(self.geometry())

    # ---------- 菜单 ----------
    def contextMenuEvent(self, event) -> None:
        menu = self._build_menu()
        menu.exec(event.globalPos())

    def _build_menu(self) -> QMenu:
        menu = QMenu(self)
        # 快捷启动子菜单
        launcher_action = QAction("快速启动", menu)
        launcher_menu = QMenu("快速启动", menu)
        items = self.callbacks.get("launcher_items", lambda: [])
        for label, fn in items():
            act = QAction(label, launcher_menu)
            act.triggered.connect(fn)
            launcher_menu.addAction(act)
        launcher_action.setMenu(launcher_menu)
        menu.addAction(launcher_action)

        menu.addSeparator()
        self._add_cb_action(menu, "token_status", "Token 余量")
        self._add_cb_action(menu, "open_note", "便利签")
        self._add_cb_action(menu, "open_log", "日志")
        self._add_cb_action(menu, "open_settings", "设置")
        menu.addSeparator()
        # 可勾选的开关类动作
        for text, (toggle_fn, is_checked_fn) in (self.callbacks.get("checkable_actions") or {}).items():
            act = QAction(text, menu)
            act.setCheckable(True)
            act.setChecked(bool(is_checked_fn()))
            act.toggled.connect(lambda checked, fn=toggle_fn: fn(checked))
            menu.addAction(act)
        menu.addSeparator()
        menu.addAction("退出", self.quit_app)
        return menu

    def _add_cb_action(self, menu: QMenu, key: str, text: str) -> None:
        fn = self.callbacks.get(key)
        if fn is None:
            return
        act = QAction(text, menu)
        act.triggered.connect(fn)
        menu.addAction(act)

    def quit_app(self) -> None:
        log.info("桌宠退出")
        if self.movie is not None:
            self.movie.stop()
        QApplication.instance().quit()

    # ---------- 托盘 ----------
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(_make_tray_icon(), self)
        self.tray.setToolTip("桌宠")
        tray_menu = QMenu()
        tray_menu.addAction("显示 / 隐藏", self.toggle_visible)
        tray_menu.addSeparator()
        self._add_tray_cb(tray_menu, "open_note", "便利签")
        self._add_tray_cb(tray_menu, "open_log", "日志")
        self._add_tray_cb(tray_menu, "open_settings", "设置")
        tray_menu.addSeparator()
        tray_menu.addAction("退出", self.quit_app)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(
            lambda reason: self.toggle_visible()
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
        self.tray.show()

    def _add_tray_cb(self, menu: QMenu, key: str, text: str) -> None:
        fn = self.callbacks.get(key)
        if fn is None:
            return
        act = QAction(text, menu)
        act.triggered.connect(fn)
        menu.addAction(act)

    def toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def set_balloon(self, title: str, message: str) -> None:
        """托盘气泡提醒（用于预警）。"""
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Warning, 8000)

    # ---------- 生命周期 ----------
    def closeEvent(self, event) -> None:
        """关窗口时隐藏到托盘而不是退出。"""
        event.ignore()
        self.hide()
