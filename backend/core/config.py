"""Application settings and path resolution."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PB_", env_file=".env", extra="ignore")

    app_name: str = "private-browser"
    api_host: str = "127.0.0.1"
    api_port: int = 8769
    api_token: str | None = None  # populated at runtime
    data_dir: Path | None = None

    def model_post_init(self, __ctx) -> None:
        if self.data_dir is None:
            base = Path(os.environ.get("APPDATA", str(Path.home())))
            object.__setattr__(self, "data_dir", base / self.app_name)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def profiles_dir(self) -> Path:
        return self.data_dir / "profiles"

    @property
    def camoufox_dir(self) -> Path:
        return self.data_dir / "camoufox"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "temp"

    def ensure_dirs(self) -> None:
        for p in [
            self.data_dir,
            self.profiles_dir,
            self.camoufox_dir,
            self.logs_dir,
            self.backups_dir,
            self.temp_dir,
        ]:
            p.mkdir(parents=True, exist_ok=True)
