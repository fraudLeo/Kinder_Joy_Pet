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
        self.setWindowTitle("super Kindar")

        size = int(self.config.get("pet_size", 100))
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
            self._mouth_open = 0.0  # 张嘴程度 0~1（鼠标越近越大）
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
    @staticmethod
    def _mouth_target(dist: float, near: float = 60.0, far: float = 350.0) -> float:
        """鼠标距离 -> 张嘴程度 0~1：far 外闭嘴，near 内最大张嘴，线性过渡。"""
        if dist <= near:
            return 1.0
        if dist >= far:
            return 0.0
        return 1.0 - (dist - near) / (far - near)

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
        center = self.frameGeometry().center()
        dist = math.hypot(pos.x() - center.x(), pos.y() - center.y())
        # 张嘴程度：越近越大，逐帧平滑过渡
        target = self._mouth_target(dist)
        self._mouth_open += (target - self._mouth_open) * 0.25
        self._eye_offset = self._compute_eye_offset(pos.x(), pos.y(), max_offset=4.0)
        self._draw_placeholder()

    def _draw_placeholder(self) -> None:
        """按参考图绘制卡比：粉球身体、两只小手、大脚、竖长黑眼（跟随鼠标）、小嘴。"""
        size = self.width()
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = size / 200.0  # 以 200px 为基准缩放
        p.setPen(Qt.PenStyle.NoPen)

        # 大脚（身体下层，底部两个深粉大椭圆，伸出底缘）
        p.setBrush(QColor(235, 124, 152))
        p.drawEllipse(int(42 * s), int(162 * s), int(56 * s), int(34 * s))
        p.drawEllipse(int(102 * s), int(162 * s), int(56 * s), int(34 * s))

        # 小手（身体两侧浅粉斜椭圆，先画、部分被身体覆盖）
        p.setBrush(QColor(238, 165, 172))
        p.save()
        p.translate(int(30 * s), int(122 * s))
        p.rotate(-30)
        p.drawEllipse(int(-14 * s), int(-8 * s), int(28 * s), int(16 * s))
        p.restore()
        p.save()
        p.translate(int(170 * s), int(122 * s))
        p.rotate(30)
        p.drawEllipse(int(-14 * s), int(-8 * s), int(28 * s), int(16 * s))
        p.restore()

        # 身体：粉色大圆——参考图浅粉 (240,205,205)
        p.setBrush(QColor(240, 205, 205))
        p.drawEllipse(int(16 * s), int(18 * s), int(168 * s), int(168 * s))

        # 嘴：随鼠标距离张合（越近越大），中心 (100,122)
        mo = max(0.0, min(self._mouth_open, 1.0))
        mw = (12.0 + 12.0 * mo) * s   # 宽 12 -> 24
        mh = (8.0 + 16.0 * mo) * s    # 高 8 -> 24
        r = int(225 - 45 * mo)
        g = int(105 - 55 * mo)
        b = int(135 - 40 * mo)
        p.setBrush(QColor(r, g, b))
        p.drawEllipse(int((100.0 * s) - mw / 2), int((122.0 * s) - mh / 2), int(mw), int(mh))

        off = self._eye_offset  # 眼珠偏移（跟随鼠标，最大 ~4px）
        blink = 1 <= self._blink_tick <= 3  # 眨眼状态机：每周期开头 3 拍闭眼
        if blink:
            # 眨眼：闭眼横条（深粉）
            p.setBrush(QColor(225, 105, 135))
            p.drawRoundedRect(int(43 * s), int(66 * s), int(30 * s), int(6 * s), 3, 3)
            p.drawRoundedRect(int(127 * s), int(66 * s), int(30 * s), int(6 * s), 3, 3)
        else:
            # 竖长黑眼：窄高椭圆（宽 30 高 44）
            ew, eh = 15.0 * s, 22.0 * s  # 半轴
            eye_l = (58.0 + off.x(), 70.0 + off.y())  # 左眼中心
            eye_r = (142.0 + off.x(), 70.0 + off.y())  # 右眼中心
            p.setBrush(QColor(45, 40, 55))
            p.drawEllipse(int(eye_l[0] * s - ew), int(eye_l[1] * s - eh), int(2 * ew), int(2 * eh))
            p.drawEllipse(int(eye_r[0] * s - ew), int(eye_r[1] * s - eh), int(2 * ew), int(2 * eh))
            # 高光（眼珠上侧偏内白圆）
            p.setBrush(QColor(255, 255, 255))
            p.drawEllipse(int(51 * s), int(60 * s), int(12 * s), int(12 * s))
            p.drawEllipse(int(135 * s), int(60 * s), int(12 * s), int(12 * s))

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
