"""冒烟测试：不起进程、不连外网。

用 Flask 的 test client 直接打 API，存储层指向一个独立的 Redis 库（见 conftest.py）。
需要本机有 Redis 在跑：

    pytest
"""

import os
import time

import pytest

from proxyproof import crawlers
from proxyproof.probe import verdict as V
from proxyproof.probe.matrix import Observation
from proxyproof.processors import server
from proxyproof.setting import PROBE_MAX_AGE
from proxyproof.storages.pool import Pool

PREFIX = "proxyproof-test"
KEY = "default"
FAKE = "203.0.113.7:8080"  # TEST-NET-3 文档专用地址，保证不会和真实代理撞上


def wipe(pool):
    keys = pool.db.keys(f"{PREFIX}:*")
    if keys:
        pool.db.delete(*keys)


@pytest.fixture
def pool():
    p = Pool(prefix=PREFIX)
    wipe(p)
    yield p
    wipe(p)


@pytest.fixture
def client(pool, monkeypatch):
    monkeypatch.setattr(server, "_pool", pool)  # API 走测试自己的池，而不是模块级默认前缀的那个
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


def observe(verdict, proxy=FAKE, **fields):
    return Observation(proxy=proxy, key=KEY, verdict=verdict, **fields)


def ok(**fields):
    return observe(V.OK, lat_ms=300, **fields)


# ---------- 不依赖网络行为的检查 ----------

def test_runs_on_isolated_db(pool):
    """测试只能跑在独立的库上，绝不能碰正在运行的池（默认 db0）"""
    kwargs = pool.db.connection_pool.connection_kwargs
    db = kwargs.get("db")
    assert db == int(os.environ["REDIS_DB"])
    assert db != 0


def test_all_crawlers_register():
    names = [c.__name__ for c in crawlers.__all__]
    assert len(names) >= 20, len(names)
    assert len(names) == len(set(names))
    for cls in crawlers.__all__:
        assert cls.urls, f"{cls.__name__} 没有配置 urls"
        assert hasattr(cls, "parse"), f"{cls.__name__} 没有 parse"


def test_ok_recheck_fits_inside_freshness_window():
    """OK 的复检间隔必须小于新鲜度闸门，否则代理会在「刚过期」和「下次复检」之间发不出去"""
    assert V.next_check_delay(V.OK) < PROBE_MAX_AGE


def test_only_repeated_dead_is_dropped():
    assert V.should_drop(V.DEAD, 3)
    assert not V.should_drop(V.DEAD, 2)
    for verdict in (V.BLOCKED, V.UNKNOWN):
        assert not V.should_drop(verdict, 99)


# ---------- API ----------

def test_index(client):
    assert client.get("/").status_code == 200


def test_empty_pool_returns_503(client):
    r = client.get("/random")
    assert r.status_code == 503
    assert r.get_json()["message"] == "pool is empty"
    assert client.get("/count").data == b"0"


def test_ok_proxy_is_served_until_reported_failed(pool, client):
    pool.add(FAKE, KEY)
    pool.record(ok())

    r = client.get("/random")
    assert r.status_code == 200 and r.text == FAKE
    assert client.get("/count").data == b"1"
    stats = client.get("/stats").get_json()[KEY]
    assert stats["fresh"] == 1 and stats["total"] == 1
    assert stats["verdicts"] == {"OK": 1}

    r = client.get("/report", query_string={"proxy": FAKE, "ok": 0})
    assert r.status_code == 200 and r.get_json()["ok"] == "0"
    assert client.get("/random").status_code == 503  # 失败反馈立即生效，不等下一轮检测

    client.get("/report", query_string={"proxy": FAKE, "ok": 1})
    assert client.get("/random").status_code == 200  # 成功反馈把它放回新鲜集合


def test_transparent_proxy_is_never_served(pool, client):
    """出口 IP 等于本机的透明代理，目标站看到的是你自己的 IP，不能发出去"""
    pool.add(FAKE, KEY)
    pool.record(ok(exit_ip="198.51.100.9", anonymous=False))
    assert client.get("/random").status_code == 503
    assert client.get("/count").data == b"1"  # 还留在池里等复检，只是不分发


def test_stale_proxy_is_not_served(pool, client):
    pool.add(FAKE, KEY)
    pool.record(ok(ts=int(time.time()) - PROBE_MAX_AGE - 30))
    assert client.get("/random").status_code == 503


def test_unknown_does_not_change_score(pool, client):
    """UNKNOWN 是探针自己出问题，不能扣代理的分"""
    pool.add(FAKE, KEY)
    pool.record(ok())
    before = pool.db.zscore(pool.k_score(KEY), FAKE)
    pool.record(observe(V.UNKNOWN, err="timeout"))
    assert pool.db.zscore(pool.k_score(KEY), FAKE) == before
    assert client.get("/random").status_code == 200


def test_dead_three_times_is_dropped(pool, client):
    pool.add(FAKE, KEY)
    for _ in range(2):
        pool.record(observe(V.DEAD))
        assert client.get("/count").data == b"1"
    pool.record(observe(V.DEAD))
    assert client.get("/count").data == b"0"


def test_report_validates_input(client):
    assert client.get("/report").status_code == 400
    assert client.get("/report", query_string={"proxy": FAKE, "ok": 2}).status_code == 400
    assert client.get("/report", query_string={"proxy": FAKE, "ok": 0}).status_code == 200


def test_bad_key_is_rejected(client):
    assert client.get("/random", query_string={"key": "bad key!"}).status_code == 400
    assert client.get("/random", query_string={"key": "nope"}).status_code == 404
