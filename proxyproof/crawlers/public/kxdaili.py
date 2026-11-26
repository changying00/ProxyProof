from pyquery import PyQuery as pq

from proxyproof.crawlers.base_list import SafeFetchCrawler
from proxyproof.crawlers.parsers import normalize_proxy
from proxyproof.schemas.proxy import Proxy


# 1=国内高匿 2=国内普通 3=国内 HTTPS
BASE_URL = 'https://www.kxdaili.com/dailiip/{type}/{page}.html'
MAX_PAGE = 2


class KxDailiCrawler(SafeFetchCrawler):
    """
    快代理免费列表 crawler, https://www.kxdaili.com/dailiip.html
    与 kuaidaili.com 不是同一家，页面是服务端渲染表格
    """
    ignore = False

    urls = [BASE_URL.format(type=type_, page=page)
            for type_ in (1, 2, 3)
            for page in range(1, MAX_PAGE + 1)]

    def parse(self, html):
        """
        parse html file to get proxies
        """
        doc = pq(html)
        for tr in doc('table tbody tr').items():
            tds = tr.find('td')
            host = tds.eq(0).text()
            port = tds.eq(1).text()
            proxy = normalize_proxy(host, port)
            if proxy:
                yield Proxy(host=proxy[0], port=proxy[1])


if __name__ == '__main__':
    crawler = KxDailiCrawler()
    for proxy in crawler.crawl():
        print(proxy)
