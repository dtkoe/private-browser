from backend.services.update_checker import UpdateChecker


class _FakeResponse:
    def __init__(self, j, status=200):
        self._j = j
        self.status_code = status

    def json(self):
        return self._j

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("err")


class _FakeClient:
    def __init__(self, r):
        self._r = r

    def get(self, url, headers=None):
        return self._r


def test_no_update():
    c = UpdateChecker(current_version="9.9.9")
    res = c.check(client=_FakeClient(_FakeResponse({"tag_name": "v0.1.0", "html_url": "x"})))
    assert res.has_update is False


def test_update_available():
    c = UpdateChecker(current_version="0.1.0")
    res = c.check(client=_FakeClient(_FakeResponse({"tag_name": "v0.5.0", "html_url": "x"})))
    assert res.has_update is True
    assert res.latest_version == "0.5.0"


def test_request_fails():
    class _Boom:
        def get(self, *a, **k):
            raise RuntimeError("net")

    c = UpdateChecker(current_version="0.1.0")
    res = c.check(client=_Boom())
    assert res.has_update is False
