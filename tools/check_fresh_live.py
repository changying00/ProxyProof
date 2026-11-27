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
# 默认目标必须和池子的探测目标（.env 里的 PROBE_TARGETS）一致，
# 否则测的是两回事。要验别的站，命令行传 URL 覆盖
TARGET = sys.argv[1] if len(sys.argv) > 1 else 'http://cp.cloudflare.com/'
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
    # 本脚本只跟本机代理池通信，绝不走系统代理。
    # 显式 build_opener(ProxyHandler({})) 可以绕过 HTTP_PROXY/HTTPS_PROXY 环境变量
    #（Clash 常驻后这两个变量会被设成 127.0.0.1:7897，不处理的话 urllib 会把
    # 对 5555 的请求也丢给 Clash，Clash 拒连回环地址 → 报一堆看不懂的错误）
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        stats = json.loads(opener.open(POOL_API + '/stats', timeout=8).read())
        proxies = opener.open(POOL_API + '/all?max_age=300', timeout=8).read().decode().splitlines()
    except OSError as e:
        print(f'连不上代理池 {POOL_API}：{e}')
        print('先确认池子在跑：docker compose up -d，然后重试。')
        return
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
