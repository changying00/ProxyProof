"""漏斗式探测矩阵

    S0 TCP      connect 0.8s      → 不通 = DEAD，成本 0.8s（旧实现要 18s）
    S1 身份     GET 明文 echo      → 1 请求同时得到 存活 / 出口IP / 延迟
    S2 目标     每个 key 一组目标   → OK 或 BLOCKED
    S3 富化     可选，24h 一次      → CONNECT 能力 / 风险分

任何一环失败立即短路，不跑后面的探测。
"""
import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

from proxyproof.probe import verdict as V
from proxyproof.probe.anonymity import classify_anonymity, parse_headers_response
from proxyproof.probe.endpoint import Baseline, targets
from proxyproof.setting import (
    PROBE_ANON_CHECK_URL,
    PROBE_CONCURRENCY,
    PROBE_IDENTITY_URL,
    PROBE_IDENTITY_URLS,
    PROBE_TCP_TIMEOUT,
    PROBE_TIMEOUT_IDENTITY,
    PROBE_TIMEOUT_TARGET,
)

IPV4 = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
IPV6 = re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{0,4}\b')


@dataclass
class Observation:
    proxy: str
    key: str = "default"
    verdict: str = V.UNKNOWN
    tcp_ms: int = -1
    lat_ms: int = -1
    exit_ip: Optional[str] = None
    target_status: int = 0
    target_len: int = 0
    anonymous: Optional[bool] = None
    anon_level: str = "unknown"  # transparent / anonymous / elite / unknown
    plain_ok: bool = False
    err: Optional[str] = None
    ts: int = field(default_factory=lambda: int(time.time()))

    def as_dict(self):
        return {
            "proxy": self.proxy, "key": self.key, "verdict": self.verdict,
            "tcp_ms": self.tcp_ms, "lat_ms": self.lat_ms, "exit_ip": self.exit_ip,
            "status": self.target_status, "len": self.target_len,
            "anonymous": self.anonymous, "plain": self.plain_ok,
            "err": self.err, "ts": self.ts,
        }


def _is_ip(text):
    """从任意文本里抠出 IPv4/IPv6（ip.3322.net 只回 IP，myip.ipip.net 回一整句）"""
    if not text:
        return None
    m = IPV4.search(text)
    if m:
        return m.group(0)
    m = IPV6.search(text)
    return m.group(0) if m else None


class Prober:
    def __init__(self, identity_url=PROBE_IDENTITY_URL, concurrency=PROBE_CONCURRENCY,
                 tcp_timeout=PROBE_TCP_TIMEOUT,
                 timeout_identity=PROBE_TIMEOUT_IDENTITY, timeout_target=PROBE_TIMEOUT_TARGET):
        self.identity_url = identity_url
        self.concurrency = concurrency
        self.tcp_timeout = tcp_timeout
        self.timeout_identity = timeout_identity
        self.timeout_target = timeout_target
        self._baseline = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=self.concurrency, ssl=False, force_close=True),
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"},
        )
        self._baseline = await Baseline(self.session).get()
        return self

    async def __aexit__(self, *exc):
        await self.session.close()

    async def _tcp(self, host, port):
        t0 = time.perf_counter()
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), self.tcp_timeout)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return int((time.perf_counter() - t0) * 1000)
        except Exception:
            return -1

    async def _get(self, url, proxy, timeout):
        t0 = time.perf_counter()
        try:
            async with self.session.get(url, proxy=f"http://{proxy}", timeout=timeout,
                                        allow_redirects=False) as r:
                body = await r.text(errors="ignore")
                return r.status, body, int((time.perf_counter() - t0) * 1000), None
        except asyncio.TimeoutError:
            return 0, "", int((time.perf_counter() - t0) * 1000), "Timeout"
        except aiohttp.ClientResponseError as e:
            return (e.status or 0), "", int((time.perf_counter() - t0) * 1000), "ResponseError"
        except Exception as e:
            return 0, "", int((time.perf_counter() - t0) * 1000), type(e).__name__

    async def probe(self, proxy, key="default"):
        obs = Observation(proxy=proxy, key=key)
        host, _, port = proxy.rpartition(":")
        if not host or not port.isdigit():
            obs.verdict, obs.err = V.DEAD, "BadFormat"
            return obs

        obs.tcp_ms = await self._tcp(host, int(port))
        if obs.tcp_ms < 0:
            obs.verdict, obs.err = V.DEAD, "TCPFail"
            return obs

        status, body, ms, err = 0, "", -1, None
        ip = None
        for url in (PROBE_IDENTITY_URLS or [self.identity_url]):
            status, body, ms, err = await self._get(url, proxy, self.timeout_identity)
            ip = _is_ip(body) if status == 200 else None
            if ip:
                break
        if ip:
            obs.plain_ok = True
            obs.exit_ip = ip
            obs.lat_ms = ms
            obs.anonymous = not self._baseline.is_self(ip)
        elif status == 407:
            # 代理要求认证：账号密码不在池子的能力范围内，直接判死
            obs.verdict, obs.err = V.DEAD, "ProxyAuth"
            return obs

        # 匿名性三级检测：请求回显请求头的端点，判断透明/匿名/高匿
        if PROBE_ANON_CHECK_URL and obs.plain_ok:
            status, body, _, err = await self._get(PROBE_ANON_CHECK_URL, proxy, self.timeout_identity)
            if status == 200:
                headers = parse_headers_response(body)
                if headers:
                    real_ip = self._baseline.exact or {""}
                    for rip in real_ip:
                        level = classify_anonymity(headers, rip)
                        if level != "transparent":
                            obs.anon_level = level
                            break
                    else:
                        obs.anon_level = "transparent"
                else:
                    obs.anon_level = "unknown"
            else:
                obs.anon_level = "unknown"

        tgts = targets(key)
        if not tgts:
            obs.verdict = V.OK if obs.plain_ok else V.UNKNOWN
            obs.err = None if obs.plain_ok else "NoTarget"
            return obs

        # 目标探测：身份探针通过就跑第一个目标；没通过也跑一次，用于区分 BLOCKED/UNKNOWN
        t = tgts[0]
        status, tbody, tms, terr = await self._get(t["url"], proxy, self.timeout_target)
        obs.target_status, obs.target_len, obs.err = status, len(tbody or ""), terr
        if obs.lat_ms < 0:
            obs.lat_ms = tms

        if V.is_target_ok(status, tbody, t.get("min_len", 0)):
            obs.verdict = V.OK
        elif obs.plain_ok:
            obs.verdict = V.BLOCKED          # 代理活着，目标不给
        elif err and err in ("Timeout", "ResponseError"):
            obs.verdict = V.UNKNOWN          # 探针侧异常
        else:
            obs.verdict = V.UNKNOWN          # 无法归因，不惩罚
        return obs

    async def probe_many(self, proxies, key="default"):
        sem = asyncio.Semaphore(self.concurrency)

        async def one(p):
            async with sem:
                return await self.probe(p, key)

        return await asyncio.gather(*(one(p) for p in proxies), return_exceptions=False)


async def probe_all(proxies, key="default", concurrency=PROBE_CONCURRENCY):
    async with Prober(concurrency=concurrency) as prober:
        return await prober.probe_many(proxies, key)
