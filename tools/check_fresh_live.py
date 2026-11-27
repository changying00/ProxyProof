"""实测当前 fresh 集合的真实可用率：对 fresh 里的代理逐个做一次目标站请求。

从 API 拿 fresh 列表，逐个经代理请求目标站，统计「拿出去立刻能用」的比例。
跑代理池不需要它，调参时用来验证。

    python tools/check_fresh_live.py [目标URL] [抽样数]
"""
import asyncio
import json
import sys
import time
import urllib.request
from collections import Counter

import aiohttp

POOL_API = 'http://127.0.0.1:5555'
TARGET = sys.argv[1] if len(sys.argv) > 1 else 'https://www.zongheng.com/'
N_SAMPLE = int(sys.argv[2]) if len(sys.argv) > 2 else 12


async def probe(sess, proxy):
    t0 = time.time()
    try:
        async with sess.get(TARGET, proxy=f'http://{proxy}', timeout=5,
                            allow_redirects=False) as resp:
            return resp.status, round(time.time() - t0, 2), None
    except Exception as e:
        return 0, round(time.time() - t0, 2), type(e).__name__


async def main():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    stats = json.loads(opener.open(POOL_API + '/stats', timeout=8).read())
    print('stats:', json.dumps(stats, ensure_ascii=False))

    proxies = opener.open(POOL_API + '/all?max_age=300', timeout=8).read().decode().splitlines()
    proxies = [p for p in proxies if p.strip()]
    n = min(N_SAMPLE, len(proxies))
    print(f'fresh 候选 {len(proxies)} 个，抽 {n} 个实测')

    conn = aiohttp.TCPConnector(limit=6, ssl=False, force_close=True)
    async with aiohttp.ClientSession(connector=conn) as sess:
        results = []
        for p in proxies[:n]:
            st, ms, err = await probe(sess, p)
            results.append((p, st, ms, err))
            print(f'  {p:22s} -> {st or err} ({ms}s)')

    c = Counter('OK' if st and st < 400 else 'FAIL' for _, st, _, _ in results)
    print(f'可用率: {c["OK"]}/{len(results)} = {c["OK"] / len(results):.0%}' if results else '无样本')


asyncio.run(main())
