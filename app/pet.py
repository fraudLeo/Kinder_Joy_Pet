"""桌宠主窗口：透明置顶、GIF/占位动画、鼠标拖拽、右键菜单与系统托盘。

功能入口通过 callbacks 注入，避免与具体业务模块强耦合。
"""
import math
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF
from PyQt6.QtGui import QAction, QColor, QIcon, QMovie, QPainter, QPixmap, QCursor
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
            self._eye_offset = QPointF(0.0, 0.0)
            self._blink_tick = 0  # 眨眼状态机：0=睁眼，1..3=眨眼过程
            self._timer = QTimer(self)  # 眨眼 tick（100ms，3 秒一周期）
            self._timer.timeout.connect(self._tick_blink)
            self._timer.start(100)
            self._follow_timer = QTimer(self)  # 眼球跟随鼠标
            self._follow_timer.timeout.connect(self._update_eye_follow)
            self._follow_timer.start(33)  # ~30fps
            self._draw_placeholder()
            if gif:
                log.warning("指定的 GIF 不存在，使用内置占位动画: %s", gif)
            else:
                log.info("未配置 GIF，使用内置占位动画")

    # ---------- 眨眼 ----------
    def _tick_blink(self) -> None:
        """眨眼状态机：每 100ms 走一拍，30 拍（3 秒）一周期，开头 3 拍闭眼。"""
        self._blink_tick = (self._blink_tick + 1) % 30
        self._draw_placeholder()

    # ---------- 眼球跟随 ----------
    def _compute_eye_offset(self, cursor_x: int, cursor_y: int, max_offset: float = 7.0) -> QPointF:
        """鼠标位置 -> 瞳孔偏移（限制在 max_offset 像素内，200px 基准）。"""
        center = self.frameGeometry().center()
        dx = cursor_x - center.x()
        dy = cursor_y - center.y()
        dist = math.hypot(dx, dy)
        if dist <= 0:
            return QPointF(0.0, 0.0)
        scale = min(max_offset / dist, 1.0)
        return QPointF(dx * scale, dy * scale)

    def _update_eye_follow(self) -> None:
        pos = QCursor.pos()
        self._eye_offset = self._compute_eye_offset(pos.x(), pos.y(), max_offset=4.0)
        self._draw_placeholder()

    def _draw_placeholder(self) -> None:
        """程序化绘制卡比风格形象：粉球身体、大眼睛（跟随鼠标）、腮红、小嘴、小脚。"""
        size = self.width()
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = size / 200.0  # 以 200px 为基准缩放
        p.setPen(Qt.PenStyle.NoPen)

        # 小脚（在身体下层，伸出底缘）——参考图深粉 (235,124,152)
        p.setBrush(QColor(235, 124, 152))
        p.drawEllipse(int(66 * s), int(176 * s), int(26 * s), int(16 * s))
        p.drawEllipse(int(108 * s), int(176 * s), int(26 * s), int(16 * s))

        # 身体：粉色大圆——参考图浅粉 (240,205,205)
        p.setBrush(QColor(240, 205, 205))
        p.drawEllipse(int(16 * s), int(18 * s), int(168 * s), int(168 * s))

        # 腮红（左右脸颊）
        p.setBrush(QColor(235, 150, 160, 180))
        p.drawEllipse(int(42 * s), int(106 * s), int(16 * s), int(10 * s))
        p.drawEllipse(int(142 * s), int(106 * s), int(16 * s), int(10 * s))

        # 嘴：小椭圆
        p.setBrush(QColor(225, 105, 135))
        p.drawEllipse(int(95 * s), int(110 * s), int(10 * s), int(6 * s))

        off = self._eye_offset  # 眼珠偏移（跟随鼠标，最大 ~4px）
        blink = 1 <= self._blink_tick <= 3  # 眨眼状态机：每周期开头 3 拍闭眼
        if blink:
            # 眨眼：闭眼横条（深粉）
            p.setBrush(QColor(225, 105, 135))
            p.drawRoundedRect(int(52 * s), int(75 * s), int(30 * s), int(6 * s), 3, 3)
            p.drawRoundedRect(int(118 * s), int(75 * s), int(30 * s), int(6 * s), 3, 3)
        else:
            # 大眼睛：黑色眼珠（跟随鼠标偏移）
            er = 15.0 * s  # 眼珠半径
            eye_l = (67.0 + off.x(), 78.0 + off.y())  # 左眼中心
            eye_r = (133.0 + off.x(), 78.0 + off.y())  # 右眼中心
            p.setBrush(QColor(45, 40, 55))
            p.drawEllipse(int(eye_l[0] * s - er), int(eye_l[1] * s - er), int(2 * er), int(2 * er))
            p.drawEllipse(int(eye_r[0] * s - er), int(eye_r[1] * s - er), int(2 * er), int(2 * er))
            # 高光（眼珠左上角）
            p.setBrush(QColor(255, 255, 255))
            p.drawEllipse(int(59 * s), int(70 * s), int(9 * s), int(9 * s))
            p.drawEllipse(int(125 * s), int(70 * s), int(9 * s), int(9 * s))

        p.end()
        self.label.setPixmap(pix)

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
