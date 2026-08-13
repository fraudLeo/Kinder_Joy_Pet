"""设置对话框：管理快捷启动应用与各 Token 厂商的 API Key，保存到 config.json。"""
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .logger import get_logger
from .providers import REGISTRY

log = get_logger(__name__)


class _AppFormDialog(QDialog):
    """添加/编辑一个快捷启动应用的小表单。"""

    def __init__(self, parent=None, name: str = "", path: str = "", args: str = ""):
        super().__init__(parent)
        self.setWindowTitle("快捷启动应用")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(name)
        self.path_edit = QLineEdit(path)
        self.path_edit.setPlaceholderText("例如 C:\\Windows\\notepad.exe 或 notepad.exe")
        self.args_edit = QLineEdit(args)
        form.addRow("名称", self.name_edit)
        form.addRow("路径", self.path_edit)
        form.addRow("参数", self.args_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str, str]:
        return (
            self.name_edit.text().strip(),
            self.path_edit.text().strip(),
            self.args_edit.text().strip(),
        )


class SettingsDialog(QDialog):
    """设置对话框。on_saved 在保存后回调（用于刷新桌宠菜单）。"""

    def __init__(self, config: dict, on_saved: callable, parent=None):
        super().__init__(parent)
        self.config = config
        self.on_saved = on_saved
        self.key_edits: dict[str, QLineEdit] = {}
        self.setWindowTitle("桌宠设置")
        self.resize(520, 420)

        tabs = QTabWidget(self)
        tabs.addTab(self._build_launcher_tab(), "快捷启动")
        tabs.addTab(self._build_provider_tab(), "Token 厂商")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ---------- 快捷启动 Tab ----------
    def _build_launcher_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        self.app_list = QListWidget(page)
        for name, item in (self.config.get("launcher") or {}).items():
            self.app_list.addItem(
                f"{name} -> {item.get('path', '')} | {item.get('args', '')}"
            )
        layout.addWidget(self.app_list)

        btns = QHBoxLayout()
        add_btn = QPushButton("添加", page)
        edit_btn = QPushButton("编辑", page)
        del_btn = QPushButton("删除", page)
        add_btn.clicked.connect(self._add_app)
        edit_btn.clicked.connect(self._edit_app)
        del_btn.clicked.connect(self._del_app)
        btns.addWidget(add_btn)
        btns.addWidget(edit_btn)
        btns.addWidget(del_btn)
        layout.addLayout(btns)
        return page

    def _selected_app(self) -> str | None:
        row = self.app_list.currentRow()
        if row < 0:
            return None
        return self.app_list.item(row).text()

    def _add_app(self) -> None:
        dlg = _AppFormDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name, path, args = dlg.values()
        if not name or not path:
            QMessageBox.warning(self, "提示", "名称和路径不能为空")
            return
        self.app_list.addItem(f"{name} -> {path} | {args}")

    def _edit_app(self) -> None:
        text = self._selected_app()
        if not text:
            return
        name, _, rest = text.partition(" -> ")
        path, _, args = rest.partition(" | ")
        dlg = _AppFormDialog(self, name, path, args)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_name, new_path, new_args = dlg.values()
        if not new_name or not new_path:
            QMessageBox.warning(self, "提示", "名称和路径不能为空")
            return
        self.app_list.currentItem().setText(
            f"{new_name} -> {new_path} | {new_args}"
        )

    def _del_app(self) -> None:
        row = self.app_list.currentRow()
        if row >= 0:
            self.app_list.takeItem(row)

    # ---------- Token 厂商 Tab ----------
    def _build_provider_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        form = QFormLayout()
        providers = self.config.get("providers") or {}
        for key in REGISTRY:
            label = REGISTRY[key].label
            edit = QLineEdit((providers.get(key) or {}).get("api_key", ""), page)
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.setPlaceholderText("留空表示不使用该厂商")
            self.key_edits[key] = edit
            form.addRow(f"{label} ({key})", edit)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    # ---------- 保存 ----------
    def _save(self) -> None:
        launcher = {}
        for row in range(self.app_list.count()):
            text = self.app_list.item(row).text()
            name, _, rest = text.partition(" -> ")
            path, _, args = rest.partition(" | ")
            if name and path:
                launcher[name] = {"path": path, "args": args}
        self.config["launcher"] = launcher
        for key, edit in self.key_edits.items():
            cfg = self.config.setdefault("providers", {}).setdefault(key, {})
            cfg["api_key"] = edit.text().strip()
        self.on_saved()
        log.info("设置已保存")
        self.accept()
