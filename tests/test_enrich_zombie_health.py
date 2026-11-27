"""IP 富化 + 僵尸清理 + 健康检查 的测试"""
import time

from proxyproof.probe import verdict as V
from proxyproof.probe.enrich import enrich
from proxyproof.probe.matrix import Observation

PREFIX = "proxyproof-test"
KEY = "default"
FAKE = "203.0.113.7:8080"


def observe(verdict, proxy=FAKE, **fields):
    return Observation(proxy=proxy, key=KEY, verdict=verdict, **fields)


# ── IP 富化 ──────────────────────────────────────────────

def test_enrich_disabled_returns_none():
    """PROBE_ENRICH_URL 为空时不调 API，直接返回 None"""
    assert enrich("8.8.8.8") is None


# ── 僵尸清理 ─────────────────────────────────────────────

def test_clean_zombies_removes_stale(pool):
    pool.add(FAKE, KEY)
    pool.record(observe(V.OK, lat_ms=100, ts=int(time.time()) - 8 * 24 * 3600))
    removed = pool.clean_zombies(KEY, ttl=7 * 24 * 3600)
    assert removed == 1
    assert pool.count(KEY) == 0


def test_clean_zombies_keeps_recent(pool):
    pool.add(FAKE, KEY)
    pool.record(observe(V.OK, lat_ms=100, ts=int(time.time())))
    removed = pool.clean_zombies(KEY, ttl=7 * 24 * 3600)
    assert removed == 0
    assert pool.count(KEY) == 1


def test_clean_zombies_keeps_never_ok(pool):
    """从未 OK 过的（没有 last_ok 字段）不删——留给探测器继续判"""
    pool.add(FAKE, KEY)
    removed = pool.clean_zombies(KEY, ttl=7 * 24 * 3600)
    assert removed == 0
    assert pool.count(KEY) == 1


# ── 健康检查 ─────────────────────────────────────────────

def test_health_returns_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert b"ok" in r.data
