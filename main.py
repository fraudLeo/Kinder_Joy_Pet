"""桌宠入口。

用法: python main.py
"""
import json
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from app.logger import get_logger, setup_logging

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

DEFAULT_CONFIG = {
    "pet_size": 200,
    "gif_path": "",  # 留空使用内置占位动画；填本地 .gif 路径后自动加载
    "token_check_interval_sec": 300,
    "token_warn_percent": 20,  # 余量低于该百分比时预警
    "providers": {},  # 厂商插件配置，如 {"deepseek": {"api_key": "...", "model": "deepseek-chat"}}
    "launcher": {},  # 快捷启动配置，如 {"记事本": {"path": "notepad.exe", "args": ""}}
    "note_folders": {},  # 便利签数据：{"默认": {"notes": [{"id": "...", "title": "...", "text": "..."}]}}
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            merged = dict(DEFAULT_CONFIG)
            merged.update(data)
            return merged
        except (json.JSONDecodeError, OSError) as exc:
            get_logger("config").error("配置加载失败，使用默认配置: %s", exc)
    return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    setup_logging()
    log = get_logger("main")
    log.info("桌宠启动")

    from PyQt6.QtGui import QIcon  # 延迟导入，避免日志模块循环依赖

    app = QApplication(sys.argv)
    app.setApplicationName("DeskPet")
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口后留在托盘

    config = load_config()

    from app.pet import DesktopPet
    from app.token_monitor import TokenMonitor
    from app.logger import LogViewerDialog
    from app.launcher import launch
    from app.settings import SettingsDialog
    from functools import partial

    def show_log():
        LogViewerDialog().exec()

    def show_token_status():
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.information(None, "Token 余量", monitor.status_text())

    def show_settings():
        SettingsDialog(config, save_config_and_refresh, pet).exec()

    note_window = None

    def open_note():
        nonlocal note_window
        from app.sticky_note import NoteWindow

        if note_window is None:
            note_window = NoteWindow(
                config,
                lambda: save_config(config),
                on_close=lambda: None,
            )
        note_window.show()
        note_window.raise_()

    # ---------- 消息气泡（微信消息提醒演示） ----------
    from app.bubbles import BubbleWindow
    from app.wechat_monitor import DummySource

    bubbles = BubbleWindow()
    demo_source = DummySource()
    demo_source.message_received.connect(bubbles.push_message)
    demo_running = [False]

    def toggle_demo(checked: bool):
        demo_running[0] = checked
        if checked:
            demo_source.start()
        else:
            demo_source.stop()

    def save_config_and_refresh():
        save_config(config)
        pet.tray.setToolTip(f"桌宠\n{monitor.status_text()}")

    def launcher_items():
        items = []
        for name, item in (config.get("launcher") or {}).items():
            path = item.get("path", "")
            args = item.get("args", "")
            if path:
                items.append((name, partial(launch, path, args)))
        return items

    pet = DesktopPet(
        config,
        callbacks={
            "launcher_items": launcher_items,
            "token_status": show_token_status,
            "open_note": open_note,
            "open_log": show_log,
            "open_settings": show_settings,
            "on_moved": bubbles.set_anchor,
            "checkable_actions": {
                "模拟微信消息": (toggle_demo, lambda: demo_running[0]),
            },
        },
    )
    pet.show()
    bubbles.set_anchor(pet.geometry())
    bubbles.show()  # 气泡窗口必须显示，否则消息只进隐藏窗口
    log.info("桌宠主窗口已显示")

    monitor = TokenMonitor(config, parent=pet)
    monitor.status_changed.connect(
        lambda: pet.tray.setToolTip(f"桌宠\n{monitor.status_text()}")
    )
    monitor.warn.connect(pet.set_balloon)
    monitor.start()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
