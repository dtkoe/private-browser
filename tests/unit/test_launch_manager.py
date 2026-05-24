import pytest

from backend.services.launch_manager import (
    Launcher,
    LaunchError,
    LaunchHandle,
    LaunchManager,
)


class FakeHandle(LaunchHandle):
    def __init__(self, pid: int):
        self._pid = pid
        self._alive = True

    @property
    def pid(self) -> int:
        return self._pid

    def is_alive(self) -> bool:
        return self._alive

    def stop(self) -> None:
        self._alive = False


class FakeLauncher(Launcher):
    def __init__(self):
        self._next_pid = 1000

    def launch(self, *, profile_id, user_data_dir, fingerprint, proxy):
        self._next_pid += 1
        return FakeHandle(self._next_pid)


def test_launch_registers_handle():
    mgr = LaunchManager(FakeLauncher())
    h = mgr.launch(profile_id="p1", user_data_dir="/tmp/p1", fingerprint={}, proxy=None)
    assert h.pid > 0
    assert mgr.is_running("p1")
    assert mgr.get_handle("p1") is h


def test_double_launch_same_profile_raises():
    mgr = LaunchManager(FakeLauncher())
    mgr.launch(profile_id="p1", user_data_dir="/tmp/p1", fingerprint={}, proxy=None)
    with pytest.raises(LaunchError, match="already running"):
        mgr.launch(profile_id="p1", user_data_dir="/tmp/p1", fingerprint={}, proxy=None)


def test_stop_removes_from_registry():
    mgr = LaunchManager(FakeLauncher())
    mgr.launch(profile_id="p1", user_data_dir="/tmp/p1", fingerprint={}, proxy=None)
    mgr.stop("p1")
    assert not mgr.is_running("p1")


def test_stop_unknown_is_noop():
    mgr = LaunchManager(FakeLauncher())
    mgr.stop("missing")


def test_running_profiles_list():
    mgr = LaunchManager(FakeLauncher())
    mgr.launch(profile_id="a", user_data_dir="/tmp/a", fingerprint={}, proxy=None)
    mgr.launch(profile_id="b", user_data_dir="/tmp/b", fingerprint={}, proxy=None)
    assert set(mgr.running_profiles()) == {"a", "b"}
