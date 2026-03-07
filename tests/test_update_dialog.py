from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication

from clyro.config.schema import Settings
from clyro.ui.settings_window import SettingsWindow
from clyro.ui.update_dialog import UpdateDialog, UpdateReadyDialog

APP = QApplication.instance() or QApplication([])


def test_update_dialog_instantiates_without_stylesheet_error():
    dialog = UpdateDialog(
        "0.1.2",
        {
            "version": "0.1.3",
            "download_url": "https://example.com/ClyroSetup.exe",
            "release_url": "https://example.com/release",
            "notes": "Release notes",
            "sha256": "a" * 64,
            "checksum_source": "checksum file",
        },
    )

    assert dialog.windowTitle() == "Clyro Update Available"
    assert dialog.choice == "later"
    dialog.deleteLater()


def test_auto_update_setting_defaults_enabled():
    assert Settings().auto_update_enabled is True


def test_settings_window_instantiates_with_loaded_theme():
    tools = SimpleNamespace(
        ffmpeg=None,
        ffprobe=None,
        ghostscript=None,
        pngquant=None,
        jpegoptim=None,
        gifsicle=None,
        mozjpeg=False,
    )
    store = SimpleNamespace(save=lambda settings: None)

    window = SettingsWindow(Settings(), store, tools)

    assert window.windowTitle() == "Clyro - Settings"
    window.deleteLater()


def test_update_ready_dialog_instantiates():
    dialog = UpdateReadyDialog("0.1.3")

    assert dialog.windowTitle() == "Update Ready"
    assert dialog.choice == "later"
    dialog.deleteLater()
