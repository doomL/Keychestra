"""Record what you hear: system sink monitor (YouTube + Keychestra mixed)."""

from __future__ import annotations

import logging
import re
import shutil
import signal
import subprocess
import threading
from datetime import datetime
from pathlib import Path

log = logging.getLogger("keychestra")


def default_record_dir() -> Path:
    """XDG Music folder (Musica / Music / …) + Keychestra — locale-aware."""
    music: Path | None = None
    if shutil.which("xdg-user-dir"):
        try:
            out = subprocess.check_output(
                ["xdg-user-dir", "MUSIC"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if out and out != Path.home().as_posix():
                music = Path(out)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    if music is None:
        # Parse user-dirs.dirs without hardcoding English "Music"
        ud = Path.home() / ".config" / "user-dirs.dirs"
        if ud.is_file():
            text = ud.read_text(encoding="utf-8", errors="replace")
            m = re.search(r'^XDG_MUSIC_DIR\s*=\s*"([^"]+)"', text, re.M)
            if m:
                music = Path(m.group(1).replace("$HOME", str(Path.home())))
    if music is None:
        music = Path.home() / "Music"
    return music / "Keychestra"


class SessionRecorder:
    """
    Captures the default audio *output* monitor via ffmpeg+Pulse/PipeWire.
    That stream is what reaches the speakers/headphones — so a YouTube tab
    and Keychestra both land in the same recording.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else default_record_dir()
        self._proc: subprocess.Popen | None = None
        self._path: Path | None = None
        self._lock = threading.Lock()

    @property
    def recording(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    @property
    def current_path(self) -> Path | None:
        return self._path

    @staticmethod
    def _default_sink_node() -> str | None:
        if not shutil.which("wpctl"):
            return None
        try:
            out = subprocess.check_output(
                ["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
        m = re.search(r'\*?\s*node\.name\s*=\s*"([^"]+)"', out)
        return m.group(1) if m else None

    @staticmethod
    def _list_pulse_monitors() -> list[str]:
        if not shutil.which("ffmpeg"):
            return []
        try:
            out = subprocess.check_output(
                ["ffmpeg", "-hide_banner", "-sources", "pulse"],
                text=True,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as exc:
            out = exc.output or ""
        monitors: list[str] = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("Auto-detected"):
                continue
            # "name [description] (none)" — monitor sources end with .monitor
            name = line.split()[0].lstrip("*").strip()
            if name.endswith(".monitor"):
                monitors.append(name)
        return monitors

    def resolve_monitor(self) -> str:
        sink = self._default_sink_node()
        if sink:
            candidate = f"{sink}.monitor"
            monitors = self._list_pulse_monitors()
            if candidate in monitors or not monitors:
                return candidate
            # fallback: any monitor whose prefix matches
            for m in monitors:
                if m.startswith(sink):
                    return m
        monitors = self._list_pulse_monitors()
        if not monitors:
            raise RuntimeError(
                "Nessun monitor audio trovato. Serve ffmpeg con Pulse/PipeWire."
            )
        return monitors[0]

    def start(self) -> Path:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                raise RuntimeError("Registrazione già in corso")
            if not shutil.which("ffmpeg"):
                raise RuntimeError("ffmpeg non trovato (sudo apt install ffmpeg)")

            monitor = self.resolve_monitor()
            self.output_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self.output_dir / f"session_{stamp}.ogg"

            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "pulse",
                "-i",
                monitor,
                "-c:a",
                "libvorbis",
                "-q:a",
                "5",
                str(path),
            ]
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self._path = path
            log.info("recording START ← %s → %s", monitor, path)
            return path

    def stop(self) -> Path | None:
        with self._lock:
            proc = self._proc
            path = self._path
            self._proc = None
            self._path = None

        if proc is None:
            return None

        # Graceful stop so the Ogg container is finalized
        try:
            proc.send_signal(signal.SIGINT)
        except Exception:
            proc.terminate()

        try:
            _, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, err = proc.communicate(timeout=2)

        if err:
            msg = err.decode("utf-8", errors="replace").strip()
            if msg:
                log.warning("ffmpeg: %s", msg)

        if path and path.is_file() and path.stat().st_size > 0:
            log.info("recording STOP → %s (%.1f KB)", path, path.stat().st_size / 1024)
        else:
            log.warning("recording STOP — file missing or empty: %s", path)
        return path
