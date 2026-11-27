"""获取器：爬虫 → 池（写 meta + 排到期）。前置验证交给 tester 的漏斗，不在这里做。"""
from loguru import logger

from proxyproof.crawlers import __all__ as crawlers_cls
from proxyproof.probe.endpoint import all_keys
from proxyproof.setting import CN_ONLY, PROXY_NUMBER_MAX
from proxyproof.storages.pool import Pool
from proxyproof.utils.cn_ip import is_cn


class Getter:
    def __init__(self):
        self.pool = Pool()
        self.crawlers_cls = crawlers_cls
        self.crawlers = [crawler_cls() for crawler_cls in crawlers_cls]
        self.keys = all_keys()

    def is_full(self):
        return self.pool.count(self.keys[0]) >= PROXY_NUMBER_MAX

    def run(self):
        if self.is_full():
            logger.info(f'pool is full ({PROXY_NUMBER_MAX}), skip crawling')
            return 0
        added = 0
        for crawler in self.crawlers:
            if self.is_full():                 # 每个爬虫前检查，避免一次灌爆到期队列
                logger.info(f'pool reached {PROXY_NUMBER_MAX}, stop crawling')
                break
            name = type(crawler).__name__
            n = 0
            try:
                for proxy in crawler.crawl():
                    if self.is_full():
                        break
                    # CN_ONLY 全局开关：整个池子只收国内 IP（源头过滤，
                    # 海外机房代理连抓都不用抓进池，探测配额全留给国内段）
                    if CN_ONLY and not is_cn(proxy.host):
                        continue
                    for key in self.keys:
                        # cn 开头的 key 是国内站专用池：只收国内段 IP，
                        # 海外机房代理进国内池只会被墙，白占探测和存储
                        if key.startswith('cn') and not is_cn(proxy.host):
                            continue
                        if self.pool.add(proxy.string(), key, src=name):
                            n += 1
            except Exception as e:
                logger.warning(f'crawler {name} failed: {e}')
            added += n
            if n:
                logger.info(f'crawler {name} added {n}')
        logger.info(f'total added {added}')
        return added


if __name__ == '__main__':
    Getter().run()
