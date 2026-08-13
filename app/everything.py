"""Everything 集成：调用 lib/es.exe 实现本地文件秒级搜索。

依赖：
- Everything（voidtools）保持运行（es.exe 通过 IPC 查询）
- lib/es.exe（命令行接口，官方下载：https://www.voidtools.com/downloads/）
"""
import os
import subprocess
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .logger import get_logger

log = get_logger(__name__)

ES_PATH = Path(__file__).resolve().parent.parent / "lib" / "es.exe"


def search(keyword: str, max_results: int = 100) -> tuple[list[str], str | None]:
    """调 es.exe 搜索，返回 (完整路径列表, 错误信息或 None)。"""
    if not ES_PATH.exists():
        return [], f"未找到 es.exe（应为 {ES_PATH}），请到 Everything 官网下载放入 lib/ 目录"
    try:
        result = subprocess.run(
            [str(ES_PATH), "-n", str(max_results), keyword],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        return [], "无法执行 es.exe（请确认 Everything 已安装）"
    except subprocess.TimeoutExpired:
        return [], "搜索超时（Everything 未响应）"
    if result.returncode != 0:
        msg = result.stderr.strip() or f"退出码 {result.returncode}"
        return [], f"es.exe 错误: {msg}"
    paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return paths, None


def open_path(path: str) -> None:
    """用系统默认程序打开文件/文件夹。"""
    try:
        os.startfile(path)  # noqa: S606 - 打开用户搜索结果，Windows 专用
        log.info("已打开: %s", path)
    except OSError as exc:
        log.error("打开失败 %s: %s", path, exc)


def format_size(path: str) -> str:
    """文件大小人性化显示（KB/MB/GB）。"""
    try:
        size = os.path.getsize(path)
    except OSError:
        return ""
    if size >= 1024 * 1024 * 1024:
        return f"{size / (1024 ** 3):.1f} GB"
    if size >= 1024 * 1024:
        return f"{size / (1024 ** 2):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size} B"


def format_mtime(path: str) -> str:
    """修改时间格式化（Everything 风格：yyyy/M/d HH:mm）。"""
    try:
        ts = os.path.getmtime(path)
    except OSError:
        return ""
    return datetime.fromtimestamp(ts).strftime("%Y/%m/%d %H:%M")


class SearchDialog(QDialog):
    """Everything 搜索对话框：关键字秒搜，表格显示（名称/路径/大小/修改时间），双击打开。"""

    STYLE = """
        QDialog {
            background: #fffaf5;
        }
        QLineEdit {
            border: 2px solid #f3d5e0;
            border-radius: 20px;
            padding: 9px 16px;
            font-size: 14px;
            background: #ffffff;
            color: #4a3540;
            selection-background-color: #ffd6e6;
        }
        QLineEdit:focus {
            border-color: #ff9bc3;
        }
        QPushButton {
            background: #ff9bc3;
            color: #ffffff;
            border: none;
            border-radius: 20px;
            padding: 9px 22px;
            font-size: 14px;
            font-weight: bold;
        }
        QPushButton:hover {
            background: #ff85b5;
        }
        QPushButton:pressed {
            background: #f075a8;
        }
        QTableWidget {
            background: #ffffff;
            border: 1px solid #f0e0ea;
            border-radius: 12px;
            font-size: 13px;
            color: #4a3540;
            gridline-color: #f8f0f4;
            outline: none;
        }
        QTableWidget::item {
            padding: 4px 8px;
        }
        QTableWidget::item:selected {
            background: #ffd6e6;
            color: #6b3a4e;
        }
        QHeaderView::section {
            background: #fff0f6;
            color: #b98aa0;
            border: none;
            border-bottom: 1px solid #f3d5e0;
            padding: 7px 10px;
            font-weight: bold;
        }
        QLabel {
            color: #c49aaf;
            font-size: 12px;
        }
    """

    COLUMNS = ["名称", "路径", "大小", "修改时间"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 搜文件（Everything）")
        self.resize(820, 520)
        self.setStyleSheet(self.STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.input_edit = QLineEdit(self)
        self.input_edit.setPlaceholderText("输入关键字，回车搜索（Everything 秒级）")
        self.input_edit.setClearButtonEnabled(True)
        search_btn = QPushButton("🔍 搜索", self)
        row.addWidget(self.input_edit, 1)
        row.addWidget(search_btn)
        layout.addLayout(row)

        self.table = QTableWidget(self)
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setSortingEnabled(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 140)
        layout.addWidget(self.table, 1)

        self.status_label = QLabel("双击或选中后回车打开文件", self)
        layout.addWidget(self.status_label)

        self.input_edit.returnPressed.connect(self.do_search)
        search_btn.clicked.connect(self.do_search)
        self.table.itemDoubleClicked.connect(self._open_item)
        QTimer.singleShot(0, self.input_edit.setFocus)

    def do_search(self) -> None:
        keyword = self.input_edit.text().strip()
        if not keyword:
            self.status_label.setText("请输入关键字")
            return
        self.status_label.setText("搜索中…")
        self.table.setRowCount(0)
        paths, err = search(keyword)
        if err:
            self.status_label.setText(f"⚠️ {err}")
            return
        if not paths:
            self.status_label.setText("未找到匹配文件")
            return
        self.table.setSortingEnabled(False)  # 填充时禁用排序
        for p in paths:
            self._add_row(p)
        self.table.setSortingEnabled(True)
        self.status_label.setText(f"共 {len(paths)} 条结果（双击打开，点击表头可排序）")

    def _add_row(self, path: str) -> None:
        is_dir = os.path.isdir(path)
        icon = "📁 " if is_dir else "📄 "
        name = os.path.basename(path.rstrip("\\/")) or path
        dirpath = str(Path(path).parent)
        size_text = "" if is_dir else format_size(path)
        time_text = format_mtime(path)

        row = self.table.rowCount()
        self.table.insertRow(row)

        name_item = QTableWidgetItem(icon + name)
        name_item.setData(Qt.ItemDataRole.UserRole, path)
        name_item.setToolTip(path)
        path_item = QTableWidgetItem(dirpath)
        path_item.setToolTip(dirpath)
        size_item = QTableWidgetItem(size_text)
        size_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        time_item = QTableWidgetItem(time_text)
        self.table.setItem(row, 0, name_item)
        self.table.setItem(row, 1, path_item)
        self.table.setItem(row, 2, size_item)
        self.table.setItem(row, 3, time_item)

    def _open_item(self, item) -> None:
        row_item = self.table.item(item.row(), 0)
        path = (
            row_item.data(Qt.ItemDataRole.UserRole) or row_item.text()
        )
        open_path(path)
