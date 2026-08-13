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


def _read_json(path: Path) -> dict:
    """读取 JSON 文件，失败返回空 dict。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as exc:
        get_logger("config").error("配置读取失败 %s: %s", path, exc)
        return {}


def _target_config_path(config: dict) -> Path:
    """确定实际写入的配置文件：指针指向的外部文件优先，否则仓库内 config.json。"""
    ext = (config or {}).get("config_path")
    if ext:
        return Path(ext)
    return CONFIG_PATH


def load_config() -> dict:
    """加载配置。仓库内 config.json 可以是指针（{"config_path": "..."}），
    指向仓库外的真实配置文件（git 管理不到，切换分支/IDE 操作都不会丢失）。
    优先级：外部文件 > 仓库内 config.json 本身 > 默认配置。
    """
    local = _read_json(CONFIG_PATH) if CONFIG_PATH.exists() else {}
    ext_path = local.get("config_path")
    if ext_path:
        ext_file = Path(ext_path)
        if ext_file.exists():
            data = _read_json(ext_file)
            merged = dict(DEFAULT_CONFIG)
            merged.update(data)
            if not merged.get("config_path"):  # 记录实际来源，供保存时写回外部
                merged["config_path"] = ext_path
            return merged
        get_logger("config").warning("config_path 指向的外部配置不存在: %s，使用本地配置", ext_path)
    merged = dict(DEFAULT_CONFIG)
    merged.update(local)
    return merged


def save_config(config: dict) -> None:
    """保存配置：有外部指针时写外部文件，否则写仓库内 config.json。"""
    target = _target_config_path(config)
    target.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    setup_logging()
    log = get_logger("main")
    log.info("桌宠启动")

    # 崩溃诊断：Qt 断言/致命消息与 Python 崩溃栈写入 logs/crash.log，
    # 若程序异常退出（如 Qt fail-fast），下次启动可从日志定位原因
    import faulthandler
    import os
    import traceback

    # Python 未捕获异常钩子：任何异常都写入日志（含 Qt 槽内未捕获）
    def _excepthook(tp, val, tb):
        log.error("未捕获异常: %s: %s", tp.__name__, val)
        log.error("".join(traceback.format_exception(tp, val, tb)))

    sys.excepthook = _excepthook

    crash_log = Path(__file__).resolve().parent / "logs" / "crash.log"
    crash_log.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Qt 消息处理器：qWarning/qCritical/qFatal（含 ASSERT 文本）逐条 flush 落盘
        from PyQt6.QtCore import qInstallMessageHandler

        def _qt_msg_handler(mtype, ctx, msg):
            try:
                with open(crash_log, "a", encoding="utf-8", errors="replace") as f:
                    f.write(f"[QtMsgType {int(mtype)}] {msg}\n")
            except Exception:  # noqa: BLE001 - 诊断写入失败忽略
                pass

        qInstallMessageHandler(_qt_msg_handler)

        fd = os.open(crash_log, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        os.dup2(fd, 2)  # 重定向 fd 2：Qt C 层的 qWarning/qFatal/ASSERT 一并写入
        sys.stderr = os.fdopen(fd, "a", encoding="utf-8", errors="replace", buffering=0)
        faulthandler.enable(sys.stderr)  # 无缓冲：崩溃瞬间内容不丢失
        faulthandler.register(  # 注册 SIGABRT 信号处理
            __import__("signal").SIGABRT, file=sys.stderr, all_threads=True
        )
    except Exception as exc:  # noqa: BLE001 - 诊断增强失败不影响运行
        log.warning("崩溃诊断初始化失败: %s", exc)

    from PyQt6.QtGui import QIcon  # 延迟导入，避免日志模块循环依赖

    app = QApplication(sys.argv)
    app.setApplicationName("DeskPet")
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口后留在托盘

    # 单实例锁：防止多个桌宠并存（多实例会导致"退出后仍有气泡"等混乱）
    from PyQt6.QtCore import QSharedMemory

    _instance_lock = QSharedMemory("DeskPet_SingleInstance")
    if not _instance_lock.create(1):
        log.warning("检测到已有桌宠实例在运行，本实例自动退出（如需重启请先退出旧实例）")
        return 0

    config = load_config()

    from app.pet import DesktopPet
    from app.token_monitor import TokenMonitor
    from app.logger import LogViewerDialog
    from app.launcher import launch
    from app.settings import SettingsDialog
    from functools import partial

    log_viewer = None  # 单实例：重复打开复用同一窗口，避免多窗口并存

    def show_log():
        # 非模态显示：日志窗口打开时桌宠仍可操作（exec 会阻塞主窗口）
        nonlocal log_viewer
        from PyQt6.QtCore import Qt

        log.info("打开日志窗口：开始")
        try:
            if log_viewer is None:
                log_viewer = LogViewerDialog()
                log_viewer.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                log_viewer.destroyed.connect(lambda: clear_log_viewer())
                log.info("打开日志窗口：LogViewerDialog 创建成功（新实例）")
            else:
                log.info("打开日志窗口：复用已有实例")
            log_viewer.show()
            log_viewer.raise_()
            log.info("打开日志窗口：已显示")
        except Exception as exc:  # noqa: BLE001 - 日志窗口异常不拖垮桌宠
            log.exception("打开日志窗口失败: %s", exc)

    def clear_log_viewer():
        nonlocal log_viewer
        log_viewer = None

    search_window = None  # Everything 搜索窗口（单实例）

    def open_search():
        nonlocal search_window
        from app.everything import SearchDialog
        from PyQt6.QtCore import Qt as _Qt

        if search_window is None:
            search_window = SearchDialog()
            search_window.setAttribute(_Qt.WidgetAttribute.WA_DeleteOnClose)
            search_window.destroyed.connect(clear_search_window)
        search_window.show()
        search_window.raise_()
        search_window.input_edit.setFocus()

    def clear_search_window():
        nonlocal search_window
        search_window = None

    web_search_window = None  # 网页搜索窗口（单实例）

    def open_web_search():
        nonlocal web_search_window
        from app.web_search import WebSearchDialog
        from PyQt6.QtCore import Qt as _Qt

        if web_search_window is None:
            web_search_window = WebSearchDialog()
            web_search_window.setAttribute(_Qt.WidgetAttribute.WA_DeleteOnClose)
            web_search_window.destroyed.connect(clear_web_search_window)
        web_search_window.show()
        web_search_window.raise_()
        web_search_window.input_edit.setFocus()

    def clear_web_search_window():
        nonlocal web_search_window
        web_search_window = None

    token_popups = []  # 非模态弹窗持有引用，防止被 GC 销毁

    def show_token_status():
        # 点开时立即触发查询并等待结果（最多 8 秒），非模态显示余额
        from PyQt6.QtCore import QEventLoop, QTimer as _Qtimer, Qt as _Qt
        from PyQt6.QtWidgets import QMessageBox

        def _all_configured_done():
            configured = [
                k for k, c in (config.get("providers") or {}).items()
                if (c or {}).get("api_key")
            ]
            return configured and all(k in monitor.results for k in configured)

        monitor.check_all()  # 异步查询所有已配置厂商
        loop = QEventLoop()
        monitor.status_changed.connect(lambda: loop.quit() if _all_configured_done() else None)
        _Qtimer.singleShot(8000, loop.quit)  # 兜底超时
        loop.exec()

        popup = QMessageBox()
        popup.setWindowTitle("Token 余量")
        popup.setText(monitor.status_text())
        popup.setStandardButtons(QMessageBox.StandardButton.Ok)
        popup.setAttribute(_Qt.WidgetAttribute.WA_DeleteOnClose)
        popup.destroyed.connect(
            lambda: token_popups.remove(popup) if popup in token_popups else None
        )
        token_popups.append(popup)
        popup.show()  # 非模态：桌宠保持可操作

    def show_settings():
        # 非模态单实例设置窗口：打开时桌宠仍可拖动
        nonlocal settings_window
        from PyQt6.QtCore import Qt as _Qt

        if settings_window is None:
            settings_window = SettingsDialog(config, save_config_and_refresh, pet)
            settings_window.setAttribute(_Qt.WidgetAttribute.WA_DeleteOnClose)
            settings_window.destroyed.connect(clear_settings_window)
        settings_window.show()
        settings_window.raise_()

    def clear_settings_window():
        nonlocal settings_window
        settings_window = None

    settings_window = None

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
            "open_search": open_search,
            "open_web_search": open_web_search,
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
    # 气泡窗口初始隐藏，收到消息时自动显示（见 bubbles.push_message）
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
