"""检测器：到期队列 + 漏斗探测

与旧实现的区别：
  - 不再全量扫描（ZSCAN 遍历时改分数会漏成员）
  - 只看到期的那批，周期与池子大小脱钩
  - 四态记录，BLOCKED / UNKNOWN 不扣分
"""
import asyncio
import time

from loguru import logger

from proxyproof.probe.endpoint import all_keys
from proxyproof.probe.matrix import Prober
from proxyproof.setting import CYCLE_TESTER, PROBE_BATCH
from proxyproof.storages.pool import Pool


class Tester(object):
    def __init__(self):
        self.pool = Pool()
        self.keys = all_keys()
        self._last_reseed = 0.0

    async def _pass(self, key, budget_until):
        popped = 0
        while time.time() < budget_until:
            proxies = self.pool.due_pop(key, PROBE_BATCH)
            if not proxies:
                break
            async with Prober() as prober:
                obs = await prober.probe_many(proxies, key)
            summary = {}
            for o in obs:
                r = self.pool.record(o)
                summary[o.verdict] = summary.get(o.verdict, 0) + 1
                if r.get("dropped"):
                    logger.info(f'{o.proxy} dropped, consecutive failures')
            popped += len(obs)
            logger.info(f'[{key}] probed {len(obs)} {summary} '
                        f'fresh={self.pool.count(key, max_age=180)} '
                        f'total={self.pool.count(key)}')
        return popped

    async def _run_once(self, budget=CYCLE_TESTER):
        budget_until = time.time() + max(5, budget - 2)
        total = 0
        for key in self.keys:
            self.pool.ensure_key(key)
            # 只有 due 队列空、池里却有代理时才可能是崩溃丢任务；频率限制到 5 分钟一次，
            # 否则每轮都会对全池做一次 ZSCAN
            if (self.pool.due_size(key) == 0 and self.pool.count(key) > 0
                    and time.time() - self._last_reseed > 300):
                n = self.pool.reseed(key)
                self._last_reseed = time.time()
                if n:
                    logger.warning(f'[{key}] reseeded {n} proxies into due queue (crash recovery)')
            total += await self._pass(key, budget_until)
        return total

    def run(self):
        return asyncio.run(self._run_once())


if __name__ == '__main__':
    Tester().run()
