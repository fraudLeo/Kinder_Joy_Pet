"""快捷启动：以独立进程启动指定应用（exe/命令/文档）。"""
import subprocess

from .logger import get_logger

log = get_logger(__name__)


def launch(path: str, args: str = "") -> str | None:
    """启动应用。成功返回 None，失败返回错误信息。"""
    cmd = [path]
    if args.strip():
        cmd += args.strip().split()
    try:
        subprocess.Popen(
            cmd,
            close_fds=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        log.info("启动应用: %s %s", path, args)
        return None
    except OSError as exc:
        log.error("启动失败 %s: %s", path, exc)
        return f"{path}: {exc}"
