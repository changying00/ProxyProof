import re

from pyquery import PyQuery as pq

from proxyproof.crawlers.base_list import SafeFetchCrawler
from proxyproof.crawlers.parsers import normalize_proxy
from proxyproof.schemas.proxy import Proxy


BASE_URL = 'https://proxydb.net/?protocol={protocol}&offset={offset}'
MAX_PAGE = 4
PAGE_SIZE = 15


class ProxyDBCrawler(SafeFetchCrawler):
    """
    proxydb crawler, https://proxydb.net/
    服务端渲染的表格，每行 3 个 td：IP / 端口 / 协议
    """
    ignore = False

    urls = [BASE_URL.format(protocol=protocol, offset=page * PAGE_SIZE)
            for protocol in ('http', 'https')
            for page in range(MAX_PAGE)]

    def parse(self, html):
        """
        parse html file to get proxies
        """
        doc = pq(html)
        for tr in doc('table tbody tr').items():
            host = tr.find('td:nth-child(1)').text()
            port = tr.find('td:nth-child(2)').text()
            # 端口列里可能带隐藏的排序数字，取第一段纯数字即可
            port = re.sub(r'\D', '', port or '')
            proxy = normalize_proxy(host, port)
            if proxy:
                yield Proxy(host=proxy[0], port=proxy[1])


if __name__ == '__main__':
    crawler = ProxyDBCrawler()
    for proxy in crawler.crawl():
        print(proxy)
