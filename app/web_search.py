"""网页搜索：关键字拼入搜索引擎 URL，调系统默认浏览器（Edge/Chrome）打开搜索结果。

设计：关键字经 URL 编码后拼接到搜索引擎查询参数中，webbrowser 使用系统默认浏览器。
"""
import webbrowser
from urllib.parse import quote_plus

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from .logger import get_logger

log = get_logger(__name__)

# 搜索引擎表：名称 -> URL 模板（{kw} 占位）
SEARCH_ENGINES = {
    "百度": "https://www.baidu.com/s?wd={kw}",
    "Google": "https://www.google.com/search?q={kw}",
    "Bing": "https://www.bing.com/search?q={kw}",
}


def build_url(keyword: str, engine: str = "百度") -> str:
    """关键字 -> 搜索引擎 URL（URL 编码后拼入查询参数）。"""
    template = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["百度"])
    return template.format(kw=quote_plus(keyword))


def open_search(keyword: str, engine: str = "百度") -> None:
    """用系统默认浏览器打开搜索结果页。"""
    url = build_url(keyword, engine)
    log.info("网页搜索 [%s] %s", engine, keyword)
    webbrowser.open(url)


class WebSearchDialog(QDialog):
    """网页搜索窗口：输入关键字，选择引擎，回车/点击在浏览器中搜索（非模态）。"""

    STYLE = """
        QDialog { background: #fffaf5; }
        QLineEdit {
            border: 2px solid #f3d5e0; border-radius: 20px;
            padding: 9px 16px; font-size: 14px; background: #ffffff; color: #4a3540;
        }
        QLineEdit:focus { border-color: #ff9bc3; }
        QPushButton {
            background: #ff9bc3; color: #ffffff; border: none;
            border-radius: 20px; padding: 9px 22px; font-size: 14px; font-weight: bold;
        }
        QPushButton:hover { background: #ff85b5; }
        QComboBox {
            border: 2px solid #f3d5e0; border-radius: 16px;
            padding: 6px 12px; background: #ffffff; color: #4a3540; font-size: 13px;
        }
        QComboBox QAbstractItemView {
            background: #ffffff; border: 1px solid #f0e0ea; selection-background-color: #ffd6e6;
        }
        QLabel { color: #c49aaf; font-size: 12px; }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 网页搜索")
        self.setStyleSheet(self.STYLE)
        self.resize(460, 130)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.input_edit = QLineEdit(self)
        self.input_edit.setPlaceholderText("输入搜索内容，回车在浏览器中打开")
        self.input_edit.setClearButtonEnabled(True)
        self.engine_combo = QComboBox(self)
        self.engine_combo.addItems(list(SEARCH_ENGINES))
        search_btn = QPushButton("搜索", self)
        row.addWidget(self.input_edit, 1)
        row.addWidget(self.engine_combo)
        row.addWidget(search_btn)
        layout.addLayout(row)

        self.status_label = QLabel("回车或点击搜索：默认浏览器打开结果页", self)
        layout.addWidget(self.status_label)

        self.input_edit.returnPressed.connect(self.do_search)
        search_btn.clicked.connect(self.do_search)
        QTimer.singleShot(0, self.input_edit.setFocus)

    def do_search(self) -> None:
        keyword = self.input_edit.text().strip()
        if not keyword:
            self.status_label.setText("请输入搜索内容")
            return
        engine = self.engine_combo.currentText()
        open_search(keyword, engine)
        self.status_label.setText(f"已在浏览器打开 {engine} 搜索：{keyword[:30]}")
