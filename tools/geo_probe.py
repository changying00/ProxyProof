"""对照实验：同一批 fresh 代理，打国外目标 vs 国内目标，看差异。

结论用来判断「探测目标的地域是否在误杀国内代理」。
"""
import asyncio
import urllib.request

import aiohttp

POOL_API = 'http://127.0.0.1:5555'

# 国外 vs 国内两个探测点（都选公开的、对海量探测友好的端点）
TARGETS = {
    'cloudflare(国外)': 'http://cp.cloudflare.com/',
    'baidu(国内)': 'https://www.baidu.com/',
    'qq(国内)': 'https://www.qq.com/',
}


async def probe(sess, proxy, url):
    t0 = asyncio.get_event_loop().time()
    try:
        async with sess.get(url, proxy=f'http://{proxy}', timeout=6,
                            allow_redirects=False) as resp:
            return resp.status, round(asyncio.get_event_loop().time() - t0, 2), None
    except Exception as e:
        return 0, round(asyncio.get_event_loop().time() - t0, 2), type(e).__name__


async def main():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    proxies = opener.open(POOL_API + '/all?max_age=300', timeout=8).read().decode().splitlines()
    proxies = [p for p in proxies if p.strip()]
    n = min(15, len(proxies))
    print(f'fresh 里取 {n} 个代理做地域对照')

    conn = aiohttp.TCPConnector(limit=5, ssl=False, force_close=True)
    async with aiohttp.ClientSession(connector=conn) as sess:
        print(f'{"proxy":22s} ' + ' '.join(f'{name.split("(")[0]:12s}' for name in TARGETS))
        for p in proxies[:n]:
            row = [f'{p:22s}']
            for _, url in TARGETS.items():
                status, ms, err = await probe(sess, p, url)
                cell = str(status) if status else str(err)[:12]
                row.append(f'{cell:12s}')
            print(' '.join(row))


asyncio.run(main())
