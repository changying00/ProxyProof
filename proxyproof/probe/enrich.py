"""IP 质量富化：入池时调用免费 API 标记风险等级。

可配置 PROBE_ENRICH_URL 留空则不富化（默认）。设置后：
  - 入池时对新代理调用一次
  - 每 24h 刷新一次（PROBE_ENRICH_TTL）
  - 结果写入 pool:meta 的 risk / asn / country 字段

用的 API 需返回 JSON，且至少包含 ip、country 字段。
推荐 ip-api.com（免费，45次/分钟）或 ipinfo.io（免费，5万/月）。
"""
import time

import requests

from proxyproof.setting import PROBE_ENRICH_TTL, PROBE_ENRICH_URL

_session = requests.Session()
_session.trust_env = False


def enrich(proxy_host: str, existing_meta: dict | None = None) -> dict | None:
    """查询 IP 质量信息，返回 {risk, asn, country} 或 None。

    已有且未过期的 meta 直接跳过，不重复调用。
    """
    if not PROBE_ENRICH_URL:
        return None

    existing_meta = existing_meta or {}
    last_enrich = existing_meta.get("enriched_at", 0)
    if existing_meta.get("risk") is not None and (time.time() - last_enrich) < PROBE_ENRICH_TTL:
        return None  # 还没过期

    url = PROBE_ENRICH_URL.format(ip=proxy_host) if "{ip}" in PROBE_ENRICH_URL else f"{PROBE_ENRICH_URL}{proxy_host}"
    try:
        r = _session.get(url, timeout=5)
        data = r.json()
        risk = data.get("risk", data.get("score", 0))
        asn = data.get("asn", data.get("as", ""))
        country = data.get("country", data.get("countryCode", ""))
        return {"risk": risk, "asn": asn, "country": country, "enriched_at": int(time.time())}
    except Exception:
        return None
