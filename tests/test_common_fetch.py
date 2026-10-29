"""collectors.common.fetch: caching rules. Never cache an empty or invalid reply (cache_ok)."""
import pytest

from collectors import common


class FakeResp:
    def __init__(self, content, status=200):
        self.content, self.status = content, status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")


class FakeSession:
    def __init__(self, *contents):
        self.contents, self.calls = list(contents), 0

    def request(self, method, url, **kw):
        self.calls += 1
        return FakeResp(self.contents[min(self.calls - 1, len(self.contents) - 1)])


@pytest.fixture
def sess(data_dir, monkeypatch):
    s = FakeSession(b"first", b"second")
    monkeypatch.setattr(common, "session", lambda: s)
    return s


def test_valid_reply_is_cached(sess):
    assert common.fetch("http://x/a", delay=0) == b"first"
    assert common.fetch("http://x/a", delay=0) == b"first"      # served from disk
    assert sess.calls == 1


def test_empty_reply_is_never_cached(data_dir, monkeypatch):
    s = FakeSession(b"", b"real")
    monkeypatch.setattr(common, "session", lambda: s)
    assert common.fetch("http://x/b", delay=0) == b""
    assert common.fetch("http://x/b", delay=0) == b"real"       # second call hit the network again
    assert s.calls == 2
    assert list(common.CACHE.glob("*.bin"))                     # and the real reply is stored now


def test_reply_rejected_by_cache_ok_is_not_cached(data_dir, monkeypatch):
    """The Census 'Missing Key' HTML page was cached for 30 days once: cache_ok prevents it."""
    s = FakeSession(b"<html>Missing Key</html>", b'[["NAME"],["x"]]')
    monkeypatch.setattr(common, "session", lambda: s)
    ok = lambda b: not b.lstrip().startswith(b"<")
    assert common.fetch("http://x/c", delay=0, cache_ok=ok).startswith(b"<html>")
    assert not list(common.CACHE.glob("*.bin"))
    assert common.fetch("http://x/c", delay=0, cache_ok=ok) == b'[["NAME"],["x"]]'
    assert s.calls == 2 and list(common.CACHE.glob("*.bin"))


def test_http_error_propagates_and_is_not_cached(data_dir, monkeypatch):
    class Bad(FakeSession):
        def request(self, *a, **k):
            self.calls += 1
            return FakeResp(b"nope", 500)
    s = Bad()
    monkeypatch.setattr(common, "session", lambda: s)
    with pytest.raises(RuntimeError):
        common.fetch("http://x/d", delay=0)
    assert not list(common.CACHE.glob("*.bin"))


def test_params_change_the_cache_key(sess):
    common.fetch("http://x/e", params={"a": 1}, delay=0)
    common.fetch("http://x/e", params={"a": 2}, delay=0)
    assert sess.calls == 2


def test_record_has_required_fields(tmp_path):
    r = common.record("S", tmp_path / "f.csv", "http://u", "licence")
    assert set(r) == {"source", "file", "url", "licence_or_terms", "retrieved_at_utc"}
