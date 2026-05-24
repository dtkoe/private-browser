from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass
class UpdateInfo:
    current_version: str
    latest_version: str | None
    has_update: bool
    release_url: str | None


def _version_tuple(v: str) -> tuple:
    parts = v.lstrip("v").split("-")[0].split(".")
    return tuple(int(p) if p.isdigit() else 0 for p in parts)


class UpdateChecker:
    def __init__(self, repo: str = "dtkoe/private-browser", current_version: str = "0.7.0"):
        self._repo = repo
        self._current = current_version

    def check(self, *, client: httpx.Client | None = None) -> UpdateInfo:
        url = f"https://api.github.com/repos/{self._repo}/releases/latest"
        try:
            c = client or httpx.Client(timeout=5.0)
            r = c.get(url, headers={"Accept": "application/vnd.github+json"})
            r.raise_for_status()
            data = r.json()
        except Exception:
            return UpdateInfo(self._current, None, False, None)

        latest = (data.get("tag_name") or "").lstrip("v")
        if not latest:
            return UpdateInfo(self._current, None, False, None)
        return UpdateInfo(
            current_version=self._current,
            latest_version=latest,
            has_update=_version_tuple(latest) > _version_tuple(self._current),
            release_url=data.get("html_url"),
        )
