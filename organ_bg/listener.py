"""Global keyboard listener that never consumes key events."""

from __future__ import annotations

import threading
from typing import Callable

from pynput import keyboard
from pynput.keyboard import Key, KeyCode


class KeyboardOrganListener:
    """
    Passive listener: OS still delivers keys to the focused app.
    We only observe press/release and trigger callbacks.
    """

    def __init__(
        self,
        on_press: Callable[[Key | KeyCode], None],
        on_release: Callable[[Key | KeyCode], None],
        ignore_repeat: bool = True,
    ) -> None:
        self._on_press = on_press
        self._on_release = on_release
        self._ignore_repeat = ignore_repeat
        self._held: set[object] = set()
        self._lock = threading.Lock()
        self._listener: keyboard.Listener | None = None

    @staticmethod
    def _key_id(key: Key | KeyCode) -> object:
        if isinstance(key, KeyCode):
            # Prefer vk so layout/shift doesn't split the same physical key
            return ("vk", key.vk) if key.vk is not None else ("ch", key.char)
        return ("named", key)

    def _handle_press(self, key: Key | KeyCode) -> None:
        kid = self._key_id(key)
        with self._lock:
            if self._ignore_repeat and kid in self._held:
                return
            self._held.add(kid)
        self._on_press(key)

    def _handle_release(self, key: Key | KeyCode) -> None:
        kid = self._key_id(key)
        with self._lock:
            self._held.discard(kid)
        self._on_release(key)

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
            suppress=False,  # critical: do not steal keys from other apps
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        with self._lock:
            self._held.clear()

    def join(self) -> None:
        if self._listener is not None:
            self._listener.join()
