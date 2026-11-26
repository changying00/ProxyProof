from pyquery import PyQuery as pq

from proxyproof.crawlers.base_list import SafeFetchCrawler
from proxyproof.crawlers.parsers import normalize_proxy
from proxyproof.schemas.proxy import Proxy

BASE_URL = 'https://advanced.name/freeproxy?page={page}'
MAX_PAGE = 3


class AdvancedNameCrawler(SafeFetchCrawler):
    """
    advanced.name crawler, https://advanced.name/freeproxy
    表格每行 td.mono.ip + td.num.mono(端口)，另有 data-copy="ip:port"
    """
    ignore = False

    urls = [BASE_URL.format(page=page) for page in range(1, MAX_PAGE + 1)]

    def parse(self, html):
        """
        parse html file to get proxies
        """
        doc = pq(html)
        for tr in doc('#freetable tbody tr').items():
            # data-copy="ip:port" 最稳，避免命中同名的序号列
            address = tr.attr('data-copy') or ''
            host, _, port = address.partition(':')
            if not host:
                host = tr.find('td.ip').text()
                port = tr.find('td:nth-child(3)').text()
            proxy = normalize_proxy(host, port)
            if proxy:
                yield Proxy(host=proxy[0], port=proxy[1])


if __name__ == '__main__':
    crawler = AdvancedNameCrawler()
    for proxy in crawler.crawl():
        print(proxy)
