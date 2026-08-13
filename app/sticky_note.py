"""便利签：左侧文件夹列表 + 右侧笔记列表/文本框，持久化到 config.json。

数据结构:
    config["note_folders"] = {
        "默认": {"notes": [{"id": "n...", "title": "...", "text": "..."}]},
        ...
    }

保存策略：切换文件夹/笔记时，先把"切换前"正在编辑的笔记写回（基于 _prev_folder /
_prev_note_row 记录，而不是切换后的当前项），再加载新内容。
"""
import time

from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .logger import get_logger

log = get_logger(__name__)

DEFAULT_FOLDER = "默认"


def _first_line(text: str, limit: int = 20) -> str:
    """笔记标题：取文本首行，过长截断。"""
    stripped = text.strip()
    if not stripped:
        return "新笔记"
    line = stripped.splitlines()[0]
    return line if len(line) <= limit else line[:limit] + "…"


class _TitleBar(QWidget):
    """窗口标题栏：承担拖动窗口的功能。"""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._drag_offset: QPoint | None = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            win = self.window()
            self._drag_offset = (
                event.globalPosition().toPoint() - win.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        event.accept()


class NoteWindow(QWidget):
    """便利签主窗口：左文件夹、右笔记。"""

    def __init__(
        self,
        config: dict,
        save_cb: callable,
        on_close: callable | None = None,
    ):
        super().__init__()
        self.config = config
        self.save_cb = save_cb
        self.on_close = on_close
        self._loading = False
        self._prev_folder: str | None = None
        self._prev_note_row: int | None = None

        folders = config.setdefault("note_folders", {})
        if DEFAULT_FOLDER not in folders:
            folders[DEFAULT_FOLDER] = {"notes": []}

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("便利签")
        self.resize(700, 480)

        self._build_ui()
        self._reload_folders()

    # ---------- UI ----------
    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QListWidget {
                background: rgba(255, 250, 220, 235);
                border: 1px solid #d8c887; border-radius: 6px;
                font-family: "Microsoft YaHei"; font-size: 13px; color: #4a3b1f;
            }
            QListWidget::item { padding: 5px 4px; }
            QListWidget::item:selected { background: #f3d879; border-radius: 4px; }
            QTextEdit {
                background: rgba(255, 255, 255, 240);
                border: 1px solid #d8c887; border-radius: 6px;
                font-family: "Microsoft YaHei"; font-size: 13px; color: #2b2616;
            }
            QPushButton {
                background: rgba(255, 250, 220, 235);
                border: 1px solid #d8c887; border-radius: 4px;
                padding: 3px 8px; color: #5a4a15;
            }
            QPushButton:hover { background: #f3d879; }
            QLabel { color: #8a7320; font-size: 11px; }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)

        title = _TitleBar(self)
        title_layout = QHBoxLayout(title)
        title_layout.setContentsMargins(4, 0, 4, 0)
        title_layout.addWidget(QLabel("便利签", title))
        title_layout.addStretch(1)
        close_btn = QPushButton("✕", title)
        close_btn.setToolTip("关闭并保存")
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)
        layout.addWidget(title)

        body = QHBoxLayout()
        layout.addLayout(body, 1)

        # 左侧：文件夹列表
        left = QVBoxLayout()
        self.folder_list = QListWidget(self)
        self.folder_list.setFixedWidth(150)
        left.addWidget(self.folder_list, 1)
        folder_btns = QHBoxLayout()
        add_folder_btn = QPushButton("+ 文件夹", self)
        rename_btn = QPushButton("重命名", self)
        del_folder_btn = QPushButton("删除", self)
        folder_btns.addWidget(add_folder_btn)
        folder_btns.addWidget(rename_btn)
        folder_btns.addWidget(del_folder_btn)
        left.addLayout(folder_btns)
        body.addLayout(left)

        # 右侧：笔记列表 + 文本框
        right = QVBoxLayout()
        note_bar = QVBoxLayout()
        note_btns = QHBoxLayout()
        add_note_btn = QPushButton("+ 笔记", self)
        del_note_btn = QPushButton("删除笔记", self)
        note_btns.addWidget(add_note_btn)
        note_btns.addWidget(del_note_btn)
        note_btns.addStretch(1)
        note_bar.addLayout(note_btns)
        self.note_list = QListWidget(self)
        self.note_list.setFlow(QListWidget.Flow.LeftToRight)
        self.note_list.setWrapping(True)
        self.note_list.setFixedHeight(64)
        self.note_list.setUniformItemSizes(True)
        note_bar.addWidget(self.note_list)
        right.addLayout(note_bar)
        self.editor = QTextEdit(self)
        right.addWidget(self.editor, 1)
        body.addLayout(right, 1)

        # 信号
        self.folder_list.currentTextChanged.connect(self._on_folder_changed)
        self.note_list.currentRowChanged.connect(self._on_note_changed)
        add_folder_btn.clicked.connect(self._add_folder)
        rename_btn.clicked.connect(self._rename_folder)
        del_folder_btn.clicked.connect(self._del_folder)
        add_note_btn.clicked.connect(self._add_note)
        del_note_btn.clicked.connect(self._del_note)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_current)
        self.editor.textChanged.connect(lambda: self._save_timer.start(800))

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(190, 165, 70, 200), 1))
        p.setBrush(QColor(255, 246, 180, 235))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)

    # ---------- 数据访问 ----------
    def current_folder(self) -> dict | None:
        item = self.folder_list.currentItem()
        if item is None:
            return None
        return self.config["note_folders"].get(item.text())

    # ---------- 刷新 ----------
    def _reload_folders(self) -> None:
        self._loading = True
        self.folder_list.clear()
        # "默认"文件夹固定在首位，其余按字典序
        folders = self.config["note_folders"]
        ordered = [DEFAULT_FOLDER] + sorted(f for f in folders if f != DEFAULT_FOLDER)
        self.folder_list.addItems(ordered)
        if self.folder_list.count():
            self.folder_list.setCurrentRow(0)
        self._loading = False
        self._prev_folder = (
            self.folder_list.currentItem().text()
            if self.folder_list.currentItem()
            else None
        )
        self._reload_notes()

    def _reload_notes(self) -> None:
        self._loading = True
        self.note_list.clear()
        folder = self.current_folder()
        if folder is not None:
            for note in folder["notes"]:
                self.note_list.addItem(note.get("title") or "新笔记")
            if self.note_list.count():
                self.note_list.setCurrentRow(0)
        self._loading = False
        self._prev_note_row = 0 if self.note_list.count() else None
        self._load_editor()

    def _load_editor(self) -> None:
        self._loading = True
        note = self._note_at(self._prev_folder, self._prev_note_row)
        self.editor.setPlainText(note.get("text", "") if note else "")
        self._loading = False

    def _note_at(self, folder_name: str | None, row: int | None) -> dict | None:
        if folder_name is None or row is None:
            return None
        folder = self.config["note_folders"].get(folder_name)
        if folder is None or row < 0 or row >= len(folder["notes"]):
            return None
        return folder["notes"][row]

    # ---------- 保存 ----------
    def _save_note(self, folder_name: str | None, row: int | None) -> bool:
        """把指定文件夹/行的笔记写回 config（内容取当前编辑器）。"""
        note = self._note_at(folder_name, row)
        if note is None:
            return False
        note["text"] = self.editor.toPlainText()
        note["title"] = _first_line(note["text"])
        if row is not None and row < self.note_list.count():
            self.note_list.item(row).setText(note["title"])
        self.save_cb()
        return True

    def _save_current(self) -> None:
        if self._loading:
            return
        self._save_note(self._prev_folder, self._prev_note_row)

    # ---------- 文件夹操作 ----------
    def _add_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "新建文件夹", "文件夹名称：")
        name = name.strip() if ok else ""
        if not name:
            return
        if name in self.config["note_folders"]:
            QMessageBox.warning(self, "提示", "同名文件夹已存在")
            return
        self.config["note_folders"][name] = {"notes": []}
        self._reload_folders()
        items = self.folder_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self.folder_list.setCurrentItem(items[0])
        self.save_cb()
        log.info("新建文件夹: %s", name)

    def _rename_folder(self) -> None:
        item = self.folder_list.currentItem()
        if item is None:
            return
        old = item.text()
        name, ok = QInputDialog.getText(self, "重命名文件夹", "新名称：", text=old)
        name = name.strip() if ok else ""
        if not name or name == old:
            return
        if name in self.config["note_folders"]:
            QMessageBox.warning(self, "提示", "同名文件夹已存在")
            return
        folders = self.config["note_folders"]
        folders[name] = folders.pop(old)
        self._reload_folders()
        items = self.folder_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self.folder_list.setCurrentItem(items[0])
        self.save_cb()
        log.info("重命名文件夹: %s -> %s", old, name)

    def _del_folder(self) -> None:
        item = self.folder_list.currentItem()
        if item is None:
            return
        name = item.text()
        if name == DEFAULT_FOLDER:
            QMessageBox.information(self, "提示", "默认文件夹不能删除")
            return
        ret = QMessageBox.question(
            self,
            "删除文件夹",
            f"删除文件夹「{name}」及其全部笔记？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            del self.config["note_folders"][name]
            self._reload_folders()
            self.save_cb()
            log.info("删除文件夹: %s", name)

    # ---------- 笔记操作 ----------
    def _add_note(self) -> None:
        folder = self.current_folder()
        if folder is None:
            return
        note = {"id": f"n{int(time.time() * 1000)}", "title": "新笔记", "text": ""}
        folder["notes"].append(note)
        self._reload_notes()
        self.note_list.setCurrentRow(self.note_list.count() - 1)
        self.editor.setFocus()
        self.save_cb()
        log.info("新建笔记")

    def _del_note(self) -> None:
        folder = self.current_folder()
        if folder is None:
            return
        row = self.note_list.currentRow()
        if row < 0:
            return
        ret = QMessageBox.question(
            self,
            "删除笔记",
            "删除当前笔记？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            del folder["notes"][row]
            self._reload_notes()
            self.save_cb()
            log.info("删除笔记")

    # ---------- 切换处理（先保存切换前的内容，再加载新内容） ----------
    def _on_folder_changed(self, name: str) -> None:
        if self._loading:
            return
        self._save_note(self._prev_folder, self._prev_note_row)
        self._prev_folder = name
        self._reload_notes()

    def _on_note_changed(self, row: int) -> None:
        if self._loading:
            return
        self._save_note(self._prev_folder, self._prev_note_row)
        self._prev_note_row = row
        self._load_editor()

    # ---------- 生命周期 ----------
    def closeEvent(self, event) -> None:
        self._save_current()
        if self.on_close is not None:
            self.on_close()
        event.accept()
