import urllib.request
from pathlib import Path
import http.client

import build_release
from clyro import __version__
from clyro.cli.commands import _dispatch
from clyro.config.schema import Settings
from clyro.core.types import OptimiseCommand
from clyro.ipc.constants import build_ipc_url
from clyro.job_queue.service import _build_cache_key
from clyro.main import check_single_instance


class _DummyResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b""


def test_cli_dispatch_uses_shared_ipc_endpoint(monkeypatch, capsys):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = request.data
        captured["timeout"] = timeout
        return _DummyResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    _dispatch("optimize", [Path("sample.jpg")], aggressive=True)

    out = capsys.readouterr().out
    assert "Successfully queued 1 file(s)." in out
    assert captured["url"] == build_ipc_url("optimize")
    assert b'"aggressive": true' in captured["payload"]
    assert captured["timeout"] == 2.0


def test_optimization_cache_key_changes_with_settings():
    command = OptimiseCommand(Path("sample.jpg"), aggressive=False, output_mode="same_folder")

    key_a = _build_cache_key(command, Settings(image_jpeg_quality=80), "hash")
    key_b = _build_cache_key(command, Settings(image_jpeg_quality=60), "hash")

    assert key_a != key_b


def test_single_instance_probe_uses_short_timeout(monkeypatch):
    captured = {}

    class _FakeConnection:
        def __init__(self, host, port, timeout):
            captured["host"] = host
            captured["port"] = port
            captured["timeout"] = timeout

        def request(self, method, path):
            captured["method"] = method
            captured["path"] = path

        def getresponse(self):
            return type("_Response", (), {"status": 200})()

    monkeypatch.setattr(http.client, "HTTPConnection", _FakeConnection)

    assert check_single_instance() is True
    assert captured["path"] == "/show"
    assert captured["timeout"] == 0.15


def test_build_release_reads_centralized_version():
    assert build_release.get_project_version() == __version__
