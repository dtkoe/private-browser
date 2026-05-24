from __future__ import annotations

from fastapi import APIRouter

from backend.services.update_checker import UpdateChecker

VERSION = "0.7.0"


def build_system_router() -> APIRouter:
    router = APIRouter(tags=["system"])

    @router.get("/api/system/info")
    def info():
        return {"version": VERSION, "name": "private-browser"}

    @router.get("/api/system/check-updates")
    def check():
        u = UpdateChecker(current_version=VERSION).check()
        return {
            "current_version": u.current_version,
            "latest_version": u.latest_version,
            "has_update": u.has_update,
            "release_url": u.release_url,
        }

    return router
