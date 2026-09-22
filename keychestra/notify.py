"""Desktop notifications (Linux notify-send)."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("keychestra")


def notify(title: str, body: str = "", *, urgency: str = "normal") -> None:
    if not shutil.which("notify-send"):
        log.info("notify: %s — %s", title, body)
        return
    cmd = [
        "notify-send",
        "--app-name=Keychestra",
        f"--urgency={urgency}",
        title,
        body,
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        log.debug("notify-send failed", exc_info=True)


def notify_recording_saved(path: Path | None) -> None:
    if path is None or not path.is_file():
        notify("Keychestra", "Recording stopped (no file)", urgency="low")
        return
    kb = path.stat().st_size / 1024
    notify(
        "Session saved",
        f"{path.name}  ({kb:.0f} KB)\n{path.parent}",
        urgency="low",
    )
