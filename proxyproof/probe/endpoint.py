"""探测端点：身份探针 + 基线 IP。

身份探针一次请求同时给出三件事：存活、出口 IP、延迟。
基线 IP 必须是一**组**而不是一个 —— 实测本机出口在 182.118.238.2/.14/.39 之间
轮换，还会切到 IPv6，拿单个 IP 比对会把正常代理判成透明。
"""
import time

from proxyproof.setting import PROBE_BASELINE_TTL, PROBE_IDENTITY_URL, PROBE_TARGETS, PROBE_TIMEOUT_IDENTITY


class Baseline:
    """直连出口 IP 的缓存集合，用于匿名性判定"""

    def __init__(self, session, url=PROBE_IDENTITY_URL, ttl=PROBE_BASELINE_TTL, samples=3):
        self.session = session
        self.url = url
        self.ttl = ttl
        self.samples = samples
        self.exact = set()
        self.prefixes = set()
        self.fetched_at = 0

    @staticmethod
    def prefix(ip):
        """/24 前缀（IPv6 取前三段）"""
        if not ip:
            return ""
        if ":" in ip:
            return ":".join(ip.split(":")[:3])
        parts = ip.split(".")
        return ".".join(parts[:3]) if len(parts) == 4 else ip

    async def get(self):
        if self.exact and (time.time() - self.fetched_at) < self.ttl:
            return self
        self.exact, self.prefixes = set(), set()
        for _ in range(self.samples):
            try:
                async with self.session.get(self.url, timeout=PROBE_TIMEOUT_IDENTITY) as r:
                    ip = (await r.text()).strip().split()[0]
                    if ip:
                        self.exact.add(ip)
                        self.prefixes.add(self.prefix(ip))
            except Exception:
                pass
        self.fetched_at = time.time()
        return self

    def is_self(self, ip):
        """出口 IP 等于本机出口，或落在本机出口的 /24 → 透明代理"""
        if not ip:
            return False
        return ip in self.exact or self.prefix(ip) in self.prefixes


def targets(key=None):
    """某个 key 的目标列表；未定义时回落到 default"""
    conf = PROBE_TARGETS.get(key) or PROBE_TARGETS.get("default") or []
    return conf


def all_keys():
    return list(PROBE_TARGETS.keys()) or ["default"]
