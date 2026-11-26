import requests
from loguru import logger
from retrying import RetryError, retry

from proxyproof.crawlers.base import BaseCrawler
from proxyproof.crawlers.parsers import iter_line_proxies
from proxyproof.schemas.proxy import Proxy
from proxyproof.setting import GET_TIMEOUT

# 不带 br：环境未安装 brotli 时，声明 br 会拿到被截断的响应体
DEFAULT_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}


class SafeFetchCrawler(BaseCrawler):
    """
    只修正抓取层：固定请求头（不带 br）+ 编码兜底，解析仍由子类实现。

    项目原来的 BaseCrawler.fetch 用 fake_headers 生成请求头，其中
    `Accept-Encoding: gzip, deflate, br` 在未安装 brotli 的环境里会让
    服务器返回 br 压缩体，requests 解不出来，页面被截断成几 KB。
    新增的源统一继承这个类，避免踩同一个坑。
    """
    headers = None
    ignore = True

    @retry(stop_max_attempt_number=3, retry_on_result=lambda x: x is None, wait_fixed=2000)
    def fetch(self, url, **kwargs):
        try:
            headers = dict(DEFAULT_HEADERS)
            headers.update(self.headers or {})
            headers.update(kwargs.pop('headers', None) or {})
            kwargs.setdefault('timeout', GET_TIMEOUT)
            kwargs.setdefault('verify', False)
            response = requests.get(url, headers=headers, **kwargs)
            if response.status_code == 200:
                if not response.encoding or response.encoding.lower() in ('iso-8859-1', 'ascii'):
                    response.encoding = response.apparent_encoding or 'utf-8'
                return response.text
        except (requests.ConnectionError, requests.ReadTimeout):
            return


class TextListCrawler(SafeFetchCrawler):
    """
    纯文本代理列表基类：每行一个 `ip:port`。

    适合 GitHub 上的公开列表、`api.proxyscrape.com`、
    `openproxylist.xyz`、`spys.me` 这类 raw 文本源。
    子类只需要声明 urls（和可选的 headers）。
    """
    # 单个源一次抓取的代理数上限，防止超大列表把一轮 getter 拖死
    max_proxies = 5000
    # 抽象基类不注册；具体站点子类在定义时自动打开
    ignore = True

    def __init_subclass__(cls, **kwargs):
        """
        自动注册只认具体站点爬虫：两个基类自己 ignore=True，
        子类定义时自动变成 ignore=False
        """
        super().__init_subclass__(**kwargs)
        cls.ignore = False

    def parse(self, html):
        """
        parse text list to get proxies
        """
        count = 0
        for host, port in iter_line_proxies(html):
            if count >= self.max_proxies:
                logger.info(f'{type(self).__name__} reached max_proxies {self.max_proxies}, stop parsing')
                return
            count += 1
            yield Proxy(host=host, port=port)

    def crawl(self):
        """
        override crawl main method
        """
        try:
            for url in self.urls:
                logger.info(f'fetching {url}')
                html = self.fetch(url)
                if not html:
                    continue
                yield from self.process(html, url)
        except RetryError:
            logger.error(
                f'crawler {self} crawled proxy unsuccessfully, '
                'please check if target url is valid or network issue')
