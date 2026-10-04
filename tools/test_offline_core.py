#!/usr/bin/env python3
"""Offline-core guard: the core tools must not open sockets.

Release checklist item: "no-network core test (CI): fails if the core
opens a socket". An autouse fixture monkeypatches ``socket.socket.connect``,
``socket.socket.connect_ex`` and ``socket.create_connection`` to raise
``OfflineCoreError`` for the duration of every test in this file, then the
tests run the repo's core operations end to end. This is a guard, not a
mock: any in-process network access fails the suite.

Intentional online paths are excluded by design:
``tools/weekly_repo_report.py`` is the weekly report fetcher — it calls
GitHub/MailerSend over HTTP/SMTP on purpose, its HTTP layer is injected as
an ``opener`` callable, and its tests mock it. Only in-process sockets are
blocked here; the fetcher is opt-in and out of scope.

Opt-out: mark a test ``@pytest.mark.network`` to run it without the socket
block (reserved for tests that intentionally exercise the network).

Run with:
    python -m pytest tools/test_offline_core.py    (from the repo root)
    python tools/test_offline_core.py              (unittest-style)
"""

from __future__ import annotations

import socket
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import pytest  # noqa: E402

import schedule  # noqa: E402
import validate_registry  # noqa: E402


class OfflineCoreError(RuntimeError):
    """Raised when core code tries to open a network connection."""


def _offline_fail(*args, **kwargs):
    raise OfflineCoreError("core opened a socket during the offline-core test")


@pytest.fixture(autouse=True)
def _block_sockets(request, monkeypatch):
    """Block all outbound sockets; opt out with ``@pytest.mark.network``."""
    if request.node.get_closest_marker("network"):
        return
    monkeypatch.setattr(socket.socket, "connect", _offline_fail)
    monkeypatch.setattr(socket.socket, "connect_ex", _offline_fail)
    monkeypatch.setattr(socket, "create_connection", _offline_fail)


def test_socket_block_is_active():
    """Sanity check: the guard itself raises on any connect attempt."""
    with pytest.raises(OfflineCoreError):
        socket.create_connection(("127.0.0.1", 1), timeout=0.01)
    with pytest.raises(OfflineCoreError):
        socket.socket().connect(("127.0.0.1", 1))


def test_validate_own_registry_offline():
    """Validate the committed registry.json against its schema — local."""
    assert validate_registry.main([]) == 0


def test_schedule_list_on_tmp_config_offline(tmp_path):
    """The scheduling registry is a local JSON file — list it offline."""
    cfg = str(tmp_path / "cfg")
    assert schedule.main(["--config-dir", cfg, "list"]) == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
