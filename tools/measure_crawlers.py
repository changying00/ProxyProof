"""测每个爬虫能抓到多少条（不写 Redis，纯统计）。

    python tools/measure_crawlers.py [每个爬虫超时秒数] [并发数]
"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from proxyproof.crawlers import __all__ as crawlers_cls

BUDGET = int(sys.argv[1]) if len(sys.argv) > 1 else 45
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 6


def run_one(cls):
    name = cls.__name__
    t0 = time.time()
    out, err = [], None
    try:
        crawler = cls()
        for p in crawler.crawl():
            out.append(f"{p.host}:{p.port}")
            if time.time() - t0 > BUDGET:
                err = "timeout"
                break
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    return {"name": name, "n": len(out), "dup": len(out) - len(set(out)),
            "secs": round(time.time() - t0, 1), "err": err, "sample": out[:2]}


def main():
    print(f"crawlers={len(crawlers_cls)} budget={BUDGET}s workers={WORKERS}", flush=True)
    rows = []
    t0 = time.time()
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(run_one, c): c for c in crawlers_cls}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            rows.append(r)
            print(f"[{i:2d}/{len(futs)}] {r['name']:26s} {r['n']:5d} 条 "
                  f"{r['secs']:5.1f}s {r['err'] or ''}", flush=True)

    allp = []
    rows.sort(key=lambda r: -r["n"])
    print("\n=== 按产量排序 ===")
    for r in rows:
        print(f"{r['name']:26s} {r['n']:5d}  ({r['secs']}s) {r['err'] or ''}")

    print(f"\n耗时 {time.time()-t0:.0f}s")
    print(f"合计（含重复）{sum(r['n'] for r in rows)}")
    print(f"去重后          {sum(r['n'] for r in rows) - sum(r['dup'] for r in rows)}")
    print(f"失败的爬虫      {sum(1 for r in rows if r['err'])}")
    print(f"零产出的爬虫    {sum(1 for r in rows if r['n'] == 0)}")


if __name__ == "__main__":
    main()
