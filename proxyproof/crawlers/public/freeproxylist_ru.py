from pyquery import PyQuery as pq

from proxyproof.crawlers.base_list import SafeFetchCrawler
from proxyproof.crawlers.parsers import normalize_proxy
from proxyproof.schemas.proxy import Proxy

BASE_URL = 'http://www.freeproxylist.ru/'


class FreeProxyListRuCrawler(SafeFetchCrawler):
    """
    freeproxylist.ru crawler, http://www.freeproxylist.ru/
    表格结构：th.tblport 放 IP，td.tblport 放端口
    """
    ignore = False

    urls = [BASE_URL]

    def parse(self, html):
        """
        parse html file to get proxies
        """
        doc = pq(html)
        for tr in doc('tbody tr').items():
            # IP 在 th.tblport，端口在紧随其后的 td.tblport
            host = tr.find('th.tblport').text()
            port = tr.find('td.tblport').text()
            proxy = normalize_proxy(host, port)
            if proxy:
                yield Proxy(host=proxy[0], port=proxy[1])


if __name__ == '__main__':
    crawler = FreeProxyListRuCrawler()
    for proxy in crawler.crawl():
        print(proxy)
