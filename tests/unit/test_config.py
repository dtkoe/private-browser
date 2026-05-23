from backend.core.config import Settings


def test_settings_default_paths_under_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    s = Settings()
    assert s.data_dir == tmp_path / "private-browser"
    assert s.db_path == s.data_dir / "app.db"
    assert s.profiles_dir == s.data_dir / "profiles"
    assert s.logs_dir == s.data_dir / "logs"


def test_settings_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("PB_DATA_DIR", str(tmp_path / "custom"))
    s = Settings()
    assert s.data_dir == tmp_path / "custom"


def test_settings_creates_data_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    s = Settings()
    s.ensure_dirs()
    for p in [s.data_dir, s.profiles_dir, s.logs_dir, s.backups_dir, s.temp_dir]:
        assert p.is_dir()
