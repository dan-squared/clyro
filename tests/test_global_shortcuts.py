import ctypes
from ctypes import wintypes

from PyQt6.QtWidgets import QApplication

from clyro.ui.global_shortcuts import GlobalHotkeyManager, parse_hotkey

APP = QApplication.instance() or QApplication([])


class _FakeApi:
    def __init__(self):
        self.registered = []
        self.unregistered = []
        self.fail_ids = set()
        self._last_error = 0

    def register_hotkey(self, hotkey_id: int, modifiers: int, virtual_key: int) -> bool:
        self.registered.append((hotkey_id, modifiers, virtual_key))
        if hotkey_id in self.fail_ids:
            self._last_error = 1409
            return False
        self._last_error = 0
        return True

    def unregister_hotkey(self, hotkey_id: int) -> bool:
        self.unregistered.append(hotkey_id)
        return True

    def last_error(self) -> int:
        return self._last_error


def test_parse_hotkey_supports_letters_and_function_keys():
    assert parse_hotkey("Ctrl+Alt+D") == (0x0002 | 0x0001, ord("D"))
    assert parse_hotkey("Shift+F12") == (0x0004, 0x70 + 11)


def test_parse_hotkey_rejects_invalid_shortcuts():
    try:
        parse_hotkey("Ctrl+D+Alt")
    except ValueError as exc:
        assert "Unsupported modifier" in str(exc)
    else:
        raise AssertionError("Expected invalid shortcut to fail")


def test_sync_registers_and_replaces_shortcuts():
    api = _FakeApi()
    manager = GlobalHotkeyManager(APP, api=api)

    first = []
    second = []
    manager.sync({"toggle": ("Ctrl+Alt+D", lambda: first.append(True))})
    manager.sync({"toggle": ("Ctrl+Alt+F12", lambda: second.append(True))})

    assert api.registered == [
        (1, 0x0002 | 0x0001, ord("D")),
        (1, 0x0002 | 0x0001, 0x70 + 11),
    ]
    assert api.unregistered == [1]
    manager.unregister_all()


def test_sync_reports_registration_failures():
    api = _FakeApi()
    manager = GlobalHotkeyManager(APP, api=api)
    api.fail_ids.add(1)

    errors = manager.sync({"toggle": ("Ctrl+Alt+D", lambda: None)})

    assert errors == {"toggle": "RegisterHotKey failed with Win32 error 1409."}
    manager.unregister_all()


def test_native_event_filter_dispatches_registered_callback(monkeypatch):
    api = _FakeApi()
    manager = GlobalHotkeyManager(APP, api=api)
    triggered = []
    manager.sync({"toggle": ("Ctrl+Alt+D", lambda: triggered.append("toggle"))})
    monkeypatch.setattr(
        "clyro.ui.global_shortcuts.QTimer.singleShot",
        staticmethod(lambda _delay, callback: callback()),
    )

    msg = wintypes.MSG()
    msg.message = 0x0312
    msg.wParam = 1

    handled, result = manager.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))

    assert handled is True
    assert result == 0
    assert triggered == ["toggle"]
    manager.unregister_all()
