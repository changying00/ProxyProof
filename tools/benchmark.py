"""代理池质量评测：跑一遍给出池子的真实可用性和性能数据。

测什么：
  1. 池子概况（total / fresh / 判定分布）
  2. 真实可用率（拿 fresh 里的代理逐个发真实请求，看成功比例）
  3. 延迟分布（p50 / p90 / p99）
  4. 稳定性（同一批代理连续测两轮，看翻转率）
  5. 透明代理检测（走代理后返回的 IP 是否和本机相同）
  6. 报告反馈闭环（/report 后池子状态变化）

用法：
    python tools/benchmark.py                        # 默认测 cp.cloudflare.com
    python tools/benchmark.py https://你的目标站/    # 测你的目标站
    python tools/benchmark.py --samples 50           # 抽 50 个
"""
import argparse
import asyncio
import json
import statistics
import time
import urllib.request

import aiohttp

POOL_API = "http://127.0.0.1:5555"
IDENTITY_URL = "http://ip.3322.net/"


def api_get(path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(POOL_API + path, timeout=8) as r:
            data = r.read()
            if r.headers.get("Content-Type", "").startswith("application/json"):
                return json.loads(data)
            return data.decode()
    except Exception as e:
        print(f"连不上 {POOL_API}{path}：{e}")
        print("先启动代理池：docker compose up -d 或 python run.py")
        raise SystemExit(1) from e


def api_get_text(path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(POOL_API + path, timeout=8) as r:
        return r.read().decode()


async def probe_one(session, proxy, url, timeout=10):
    t0 = time.monotonic()
    try:
        async with session.get(url, proxy=f"http://{proxy}", timeout=aiohttp.ClientTimeout(total=timeout),
                               allow_redirects=False) as resp:
            body = await resp.text(errors="ignore")
            ms = int((time.monotonic() - t0) * 1000)
            return {"proxy": proxy, "ok": True, "status": resp.status, "ms": ms, "len": len(body)}
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        return {"proxy": proxy, "ok": False, "status": 0, "ms": ms, "err": type(e).__name__}


async def get_exit_ip(session, proxy):
    try:
        async with session.get(IDENTITY_URL, proxy=f"http://{proxy}", timeout=aiohttp.ClientTimeout(total=6)) as r:
            return (await r.text()).strip().split()[0]
    except Exception:
        return None


async def bench_round(proxies, target, concurrency=25):
    conn = aiohttp.TCPConnector(limit=concurrency, ssl=False, force_close=True)
    async with aiohttp.ClientSession(connector=conn) as session:
        sem = asyncio.Semaphore(concurrency)

        async def run(p):
            async with sem:
                return await probe_one(session, p, target)

        return await asyncio.gather(*(run(p) for p in proxies))


def fmt_ms(values):
    if not values:
        return "n/a"
    s = sorted(values)
    return f"p50={s[len(s)//2]}ms p90={s[int(len(s)*0.9)]}ms p99={s[-1]}ms"


def main():
    parser = argparse.ArgumentParser(description="代理池质量评测")
    parser.add_argument("target", nargs="?", default="http://cp.cloudflare.com/")
    parser.add_argument("--samples", type=int, default=30, help="抽样数量（默认 30）")
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument("--rounds", type=int, default=2, help="测几轮（看稳定性）")
    args = parser.parse_args()

    target = args.target
    n = args.samples

    # ── 1. 池子概况 ──────────────────────────────────────────────
    print("=" * 60)
    print("  代理池质量评测报告")
    print("=" * 60)
    stats_raw = api_get("/stats")
    print("\n【1】池子概况")
    for key, s in stats_raw.items():
        v = s.get("verdicts", {})
        total = s.get("total", 0)
        fresh = s.get("fresh", 0)
        print(f"  key={key:10s}  total={total:5d}  fresh={fresh:4d}  "
              f"verdicts: OK={v.get('OK',0)} BLOCKED={v.get('BLOCKED',0)} "
              f"DEAD={v.get('DEAD',0)} UNKNOWN={v.get('UNKNOWN',0)}")

    # 取 fresh 代理列表
    raw = api_get_text("/all?max_age=300")
    proxies = [p for p in raw.strip().splitlines() if p.strip()]
    if not proxies:
        print("\n  fresh 为空，等池子跑热后再测。")
        return
    sample = proxies[:n]
    print(f"\n  fresh 总数 {len(proxies)}，抽 {len(sample)} 个实测")

    # ── 2. 真实可用率 ──────────────────────────────────────────
    print(f"\n【2】真实可用率（目标: {target}）")
    all_ms = []
    all_ok = []
    for rnd in range(args.rounds):
        results = asyncio.run(bench_round(sample, target, args.concurrency))
        ok_count = sum(1 for r in results if r["ok"])
        ms_list = [r["ms"] for r in results if r["ok"]]
        all_ms.extend(ms_list)
        all_ok.extend(results)
        pct = ok_count / len(results) * 100 if results else 0
        print(f"  第 {rnd+1} 轮: {ok_count}/{len(results)} 成功 ({pct:.0f}%)  延迟 {fmt_ms(ms_list)}")
        if rnd < args.rounds - 1:
            time.sleep(3)

    # ── 3. 延迟分布 ────────────────────────────────────────────
    print(f"\n【3】延迟分布（{len(all_ms)} 个成功样本）")
    if all_ms:
        print(f"  {fmt_ms(all_ms)}  avg={statistics.mean(all_ms):.0f}ms")
    else:
        print("  无成功样本")

    # ── 4. 稳定性（翻转率）────────────────────────────────────
    if args.rounds >= 2:
        print(f"\n【4】稳定性（连续 {args.rounds} 轮）")
        by_proxy = {}
        for r in all_ok:
            by_proxy.setdefault(r["proxy"], []).append(r["ok"])
        flipped = sum(1 for statuses in by_proxy.values() if len(set(statuses)) > 1)
        stable = sum(1 for statuses in by_proxy.values() if all(statuses))
        dead = sum(1 for statuses in by_proxy.values() if not any(statuses))
        print(f"  稳定可用（{args.rounds}/{args.rounds} 全成功）: {stable}")
        print(f"  稳定失败（{args.rounds}/{args.rounds} 全失败）: {dead}")
        print(f"  翻转（时好时坏）: {flipped}")
        print(f"  翻转率: {flipped}/{len(by_proxy)} = {flipped/len(by_proxy)*100:.0f}%" if by_proxy else "")

    # ── 5. 透明代理检测 ────────────────────────────────────────
    print("\n【5】透明代理检测（抽 5 个看出口 IP）")
    async def check_transparent():
        conn = aiohttp.TCPConnector(limit=5, ssl=False, force_close=True)
        async with aiohttp.ClientSession(connector=conn) as session:
            tasks = []
            for p in sample[:5]:
                tasks.append(get_exit_ip(session, p))
            return await asyncio.gather(*tasks)
    exit_ips = asyncio.run(check_transparent())
    for p, ip in zip(sample[:5], exit_ips):
        tag = "⚠️ 透明代理" if ip and ip.startswith(("192.168", "10.", "172.")) else "✓"
        print(f"  {p:24s} 出口={ip or '无法获取'}  {tag}")

    # ── 6. /report 反馈闭环 ───────────────────────────────────
    print("\n【6】/report 反馈闭环")
    if sample:
        test_proxy = sample[0]
        before = api_get("/stats")
        before_fresh = before.get("default", {}).get("fresh", 0)
        # 上报失败
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        opener.open(f"{POOL_API}/report?proxy={test_proxy}&ok=0", timeout=5)
        after_fail = api_get("/stats")
        after_fail_fresh = after_fail.get("default", {}).get("fresh", 0)
        # 上报成功
        opener.open(f"{POOL_API}/report?proxy={test_proxy}&ok=1", timeout=5)
        after_ok = api_get("/stats")
        after_ok_fresh = after_ok.get("default", {}).get("fresh", 0)
        print(f"  报告失败 {test_proxy}: fresh {before_fresh} → {after_fail_fresh}  "
              f"{'✓ 已摘出' if after_fail_fresh < before_fresh else '（可能不在 fresh 中）'}")
        print(f"  报告成功 {test_proxy}: fresh {after_fail_fresh} → {after_ok_fresh}  "
              f"{'✓ 恢复' if after_ok_fresh > after_fail_fresh else '（未变化）'}")

    # ── 7. 最终评分 ────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    ok_pct = sum(1 for r in all_ok if r["ok"]) / max(len(all_ok), 1) * 100
    avg_lat = statistics.mean(all_ms) if all_ms else 9999
    print("  综合评分")
    print(f"  可用率: {ok_pct:.0f}%  平均延迟: {avg_lat:.0f}ms")
    if ok_pct >= 60 and avg_lat < 3000:
        print("  评级: ★★★★ 优秀")
    elif ok_pct >= 40:
        print("  评级: ★★★ 良好")
    elif ok_pct >= 20:
        print("  评级: ★★ 一般")
    else:
        print("  评级: ★ 较差（建议调小 PROBE_MAX_AGE 或增加池子上限）")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
