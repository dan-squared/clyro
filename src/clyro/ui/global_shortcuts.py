from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import QAbstractNativeEventFilter, QTimer
from PyQt6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

_MODIFIER_MAP = {
    "ALT": MOD_ALT,
    "CTRL": MOD_CONTROL,
    "CONTROL": MOD_CONTROL,
    "SHIFT": MOD_SHIFT,
    "WIN": MOD_WIN,
    "META": MOD_WIN,
    "SUPER": MOD_WIN,
}

_KEY_ALIASES = {
    "ESC": "ESCAPE",
    "DEL": "DELETE",
    "INS": "INSERT",
    "RETURN": "ENTER",
    "PGUP": "PAGEUP",
    "PGDN": "PAGEDOWN",
    "LEFTARROW": "LEFT",
    "RIGHTARROW": "RIGHT",
    "UPARROW": "UP",
    "DOWNARROW": "DOWN",
}

_KEY_MAP = {
    "BACKSPACE": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "PAUSE": 0x13,
    "CAPSLOCK": 0x14,
    "ESCAPE": 0x1B,
    "SPACE": 0x20,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "END": 0x23,
    "HOME": 0x24,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "PRINTSCREEN": 0x2C,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
}


@dataclass(slots=True)
class _ShortcutBinding:
    name: str
    shortcut: str
    hotkey_id: int
    callback: Callable[[], None]


class _User32HotkeyApi:
    def __init__(self):
        self._dll = ctypes.WinDLL("user32", use_last_error=True)
        self._register_hotkey = self._dll.RegisterHotKey
        self._register_hotkey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        self._register_hotkey.restype = wintypes.BOOL
        self._unregister_hotkey = self._dll.UnregisterHotKey
        self._unregister_hotkey.argtypes = [wintypes.HWND, ctypes.c_int]
        self._unregister_hotkey.restype = wintypes.BOOL

    def register_hotkey(self, hotkey_id: int, modifiers: int, virtual_key: int) -> bool:
        ctypes.set_last_error(0)
        return bool(self._register_hotkey(None, hotkey_id, modifiers | MOD_NOREPEAT, virtual_key))

    def unregister_hotkey(self, hotkey_id: int) -> bool:
        ctypes.set_last_error(0)
        return bool(self._unregister_hotkey(None, hotkey_id))

    @staticmethod
    def last_error() -> int:
        return ctypes.get_last_error()


def parse_hotkey(shortcut: str) -> tuple[int, int]:
    tokens = [_normalize_token(part) for part in shortcut.split("+") if part.strip()]
    if len(tokens) < 2:
        raise ValueError("Shortcut must include at least one modifier and one key.")

    modifiers = 0
    for token in tokens[:-1]:
        try:
            modifiers |= _MODIFIER_MAP[token]
        except KeyError as exc:
            raise ValueError(f"Unsupported modifier '{token}'.") from exc

    if modifiers == 0:
        raise ValueError("Shortcut must include at least one modifier.")

    return modifiers, _parse_virtual_key(tokens[-1])


def _normalize_token(token: str) -> str:
    return token.strip().replace(" ", "").replace("_", "").replace("-", "").upper()


def _parse_virtual_key(token: str) -> int:
    token = _KEY_ALIASES.get(token, token)

    if len(token) == 1 and token.isalpha():
        return ord(token.upper())
    if len(token) == 1 and token.isdigit():
        return ord(token)
    if token.startswith("F") and token[1:].isdigit():
        number = int(token[1:])
        if 1 <= number <= 24:
            return 0x70 + number - 1

    try:
        return _KEY_MAP[token]
    except KeyError as exc:
        raise ValueError(f"Unsupported key '{token}'.") from exc


class GlobalHotkeyManager(QAbstractNativeEventFilter):
    def __init__(self, app: QApplication, *, api: _User32HotkeyApi | None = None):
        super().__init__()
        self._app = app
        if api is not None:
            self._api = api
        elif sys.platform == "win32":
            try:
                self._api = _User32HotkeyApi()
            except Exception as exc:
                logger.warning("Global hotkeys disabled because initialization failed: %s", exc)
                self._api = None
        else:
            self._api = None
        self._bindings: dict[str, _ShortcutBinding] = {}
        self._bindings_by_id: dict[int, _ShortcutBinding] = {}
        self._name_to_id: dict[str, int] = {}
        self._next_id = 1
        self._filter_installed = False

    def sync(self, bindings: dict[str, tuple[str, Callable[[], None]]]) -> dict[str, str]:
        errors: dict[str, str] = {}

        if self._api is None:
            return errors

        wanted_names = set(bindings)
        for name in list(self._bindings):
            if name not in wanted_names:
                self._unregister_name(name)

        if bindings:
            self._ensure_event_filter()

        for name, (shortcut, callback) in bindings.items():
            normalized_shortcut = shortcut.strip()
            existing = self._bindings.get(name)
            if existing and existing.shortcut == normalized_shortcut:
                self._bindings[name] = _ShortcutBinding(name, existing.shortcut, existing.hotkey_id, callback)
                self._bindings_by_id[existing.hotkey_id] = self._bindings[name]
                continue

            if existing:
                self._unregister_name(name)

            if not normalized_shortcut:
                continue

            try:
                modifiers, virtual_key = parse_hotkey(normalized_shortcut)
            except ValueError as exc:
                message = str(exc)
                logger.warning("Skipping invalid global shortcut %s=%r: %s", name, normalized_shortcut, message)
                errors[name] = message
                continue

            hotkey_id = self._name_to_id.get(name)
            if hotkey_id is None:
                hotkey_id = self._allocate_hotkey_id()
                self._name_to_id[name] = hotkey_id
            if not self._api.register_hotkey(hotkey_id, modifiers, virtual_key):
                error_code = self._api.last_error()
                message = f"RegisterHotKey failed with Win32 error {error_code}."
                logger.warning("Unable to register global shortcut %s=%r: %s", name, normalized_shortcut, message)
                errors[name] = message
                continue

            binding = _ShortcutBinding(name, normalized_shortcut, hotkey_id, callback)
            self._bindings[name] = binding
            self._bindings_by_id[hotkey_id] = binding

        if not self._bindings:
            self._remove_event_filter()

        return errors

    def unregister_all(self):
        for name in list(self._bindings):
            self._unregister_name(name)
        self._remove_event_filter()

    def nativeEventFilter(self, event_type, message):
        if self._api is None or not self._bindings_by_id or message is None:
            return False, 0

        try:
            msg = wintypes.MSG.from_address(int(message))
        except (TypeError, ValueError):
            return False, 0

        if msg.message != WM_HOTKEY:
            return False, 0

        binding = self._bindings_by_id.get(int(msg.wParam))
        if binding is None:
            return False, 0

        QTimer.singleShot(0, binding.callback)
        return True, 0

    def _allocate_hotkey_id(self) -> int:
        hotkey_id = self._next_id
        self._next_id += 1
        return hotkey_id

    def _ensure_event_filter(self):
        if self._filter_installed:
            return
        self._app.installNativeEventFilter(self)
        self._filter_installed = True

    def _remove_event_filter(self):
        if not self._filter_installed:
            return
        self._app.removeNativeEventFilter(self)
        self._filter_installed = False

    def _unregister_name(self, name: str):
        binding = self._bindings.pop(name, None)
        if binding is None:
            return
        self._bindings_by_id.pop(binding.hotkey_id, None)
        self._api.unregister_hotkey(binding.hotkey_id)
