"""消息气泡：跟随桌宠的消息提醒队列。

- 气泡卡片：左上角发送者（加粗）+ 冒号 + 消息内容
- 多条消息从底部往上堆叠，新消息在最底下；插入/上移带果冻弹性动画 (OutBounce)
- 卡片超时自动淡出，超出上限移除最老，点击可立即关闭
- 窗口锚定在桌宠上方居中（超出屏幕顶部时移到桌宠下方）
"""
import html

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QGraphicsOpacityEffect

from .logger import get_logger

log = get_logger(__name__)


class BubbleCard(QWidget):
    """单条消息气泡卡片。"""

    LABEL_WIDTH = 300  # 内容区宽度
    PAD_X, PAD_Y = 14, 10

    def __init__(self, msg: dict, parent: QWidget):
        super().__init__(parent)
        self.msg = msg
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        sender = msg.get("sender", "未知")
        content = msg.get("content", "")
        rich = (
            f"<b style='color:#2b6cb0'>{html.escape(sender)}</b>"
            f"<span style='color:#888'>: </span>"
            f"<span>{html.escape(content)}</span>"
        )
        self.label = QLabel(rich, self)
        self.label.setWordWrap(True)
        font = QFont("Microsoft YaHei", 10)
        self.label.setFont(font)
        self.label.setStyleSheet("color:#2d2d2d; background: transparent;")

        h = self.label.heightForWidth(self.LABEL_WIDTH)
        if h <= 0:  # 兜底：按单行估算
            h = QFontMetrics(font).height() + 4
        self.setFixedSize(self.LABEL_WIDTH + 2 * self.PAD_X, h + 2 * self.PAD_Y)
        self.label.setGeometry(self.PAD_X, self.PAD_Y, self.LABEL_WIDTH, h)

        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)
        self.opacity.setOpacity(1.0)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(180, 200, 230, 200), 1))
        p.setBrush(QColor(255, 255, 255, 240))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

    def mousePressEvent(self, event) -> None:
        # 点击立即关闭本气泡
        win = self.window()
        if hasattr(win, "expire_card"):
            win.expire_card(self)
        event.accept()


class BubbleWindow(QWidget):
    """气泡队列窗口：绝对定位卡片，底部是最新消息。"""

    MAX_CARDS = 4
    CARD_GAP = 6
    TIMEOUT_MS = 8000

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # 透明区域不拦截鼠标（卡片作为子控件仍可点击）
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowTitle("消息气泡")
        self.cards: list[BubbleCard] = []  # 旧 -> 新
        self._expiring: set[BubbleCard] = set()  # 正在淡出中的卡片（去重）
        self._anchor_geo: QRect | None = None

    # ---------- 对外接口 ----------
    def set_anchor(self, pet_geo: QRect) -> None:
        """设置锚定（桌宠几何位置），气泡窗口自动跟随。"""
        self._anchor_geo = QRect(pet_geo)
        if not self.cards:
            # 空队列：收缩到最小并定位，避免遗留 640x480 透明窗口挡鼠标
            self.setFixedSize(1, 1)
        self.anchor_to(pet_geo)

    def push_message(self, msg: dict) -> None:
        card = BubbleCard(msg, self)
        card.show()
        card.opacity.setOpacity(0.0)
        self.cards.append(card)
        if not self.isVisible():
            self.show()  # 空队列时窗口隐藏，收到消息再显示
        self._relayout(animate=True, entering=card)
        QTimer.singleShot(self.TIMEOUT_MS, lambda: self.expire_card(card))
        # 超出上限：最老的正常淡出；若已在淡出中则立即完成移除（防快速连续消息累积）
        while len(self.cards) > self.MAX_CARDS:
            oldest = self.cards[0]
            if oldest in self._expiring:
                self._remove_card(oldest)
            else:
                self.expire_card(oldest)
        log.info("气泡消息 [%s] %s", msg.get("sender"), msg.get("content"))

    def expire_card(self, card: BubbleCard) -> None:
        """淡出并移除卡片（同一卡片只触发一次）。

        动画 parent 设为卡片本身：卡片被挤出/删除时动画随卡片安全销毁，
        避免动画对已删除对象操作触发 Qt fail-fast (0xc0000409)。
        """
        if card not in self.cards or card in self._expiring:
            return
        self._expiring.add(card)
        fade = QPropertyAnimation(card.opacity, b"opacity", card)
        fade.setDuration(350)
        fade.setStartValue(card.opacity.opacity())
        fade.setEndValue(0.0)
        fade.finished.connect(lambda: self._remove_card(card))
        fade.start()

    # ---------- 布局与动画 ----------
    def _remove_card(self, card: BubbleCard) -> None:
        if card not in self.cards:
            return
        self.cards.remove(card)
        self._expiring.discard(card)
        card.deleteLater()
        if not self.cards:
            self.hide()  # 队列清空后隐藏，避免常驻透明窗口
        else:
            self._relayout(animate=True)

    def _relayout(self, animate: bool = True, entering: BubbleCard | None = None) -> None:
        """从底部往上排布卡片；animate=True 时做果冻弹性动画。"""
        if not self.cards:
            self.setFixedSize(1, 1)
            self._apply_anchor()
            return
        total_h = sum(c.height() for c in self.cards) + self.CARD_GAP * (len(self.cards) - 1)
        w = max(c.width() for c in self.cards)
        self.setFixedSize(w, total_h)

        # 目标 y：从底部往上
        targets: dict[int, int] = {}
        cursor = total_h
        for c in reversed(self.cards):
            cursor -= c.height()
            targets[id(c)] = cursor
            cursor -= self.CARD_GAP

        # 每个卡片的动画 parent 设为卡片本身：卡片被删除时动画随卡片安全销毁，
        # 避免 QParallelAnimationGroup 在目标对象删除后继续运行触发 fail-fast。
        for c in self.cards:
            ty = targets[id(c)]
            if not animate:
                c.move(0, ty)
                continue
            anim = QPropertyAnimation(c, b"geometry", c)
            anim.setDuration(240)
            anim.setEasingCurve(QEasingCurve.Type.OutBounce)  # 果冻弹性
            if c is entering:
                anim.setStartValue(QRect(0, total_h, c.width(), c.height()))
                fade = QPropertyAnimation(c.opacity, b"opacity", c)
                fade.setDuration(200)
                fade.setStartValue(0.0)
                fade.setEndValue(1.0)
                fade.start()
            else:
                anim.setStartValue(c.geometry())
            anim.setEndValue(QRect(0, ty, c.width(), c.height()))
            anim.start()

        self._apply_anchor()

    def _apply_anchor(self) -> None:
        if self._anchor_geo is not None:
            self.anchor_to(self._anchor_geo)

    # ---------- 锚定 ----------
    def anchor_to(self, pet_geo: QRect) -> None:
        """锚定在桌宠正上方居中；放不下时移到桌宠下方。"""
        x = pet_geo.x() + (pet_geo.width() - self.width()) // 2
        y = pet_geo.y() - self.height() - 10
        screen = QApplication.primaryScreen().availableGeometry()
        if y < screen.top():
            y = pet_geo.y() + pet_geo.height() + 10
        self.move(x, y)
