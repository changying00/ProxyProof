from pyquery import PyQuery as pq

from proxyproof.crawlers.base_list import SafeFetchCrawler
from proxyproof.crawlers.parsers import normalize_proxy
from proxyproof.schemas.proxy import Proxy


BASE_URL = 'https://www.89ip.cn/index_{page}.html'
MAX_PAGE = 5


class Ip89WebCrawler(SafeFetchCrawler):
    """
    89ip 网页版 crawler, https://www.89ip.cn/
    原有 ip89.py 走的是 tqdl.html 接口（该接口已开始返回 521 反爬页），
    这里补网页版：服务端渲染的 layui 表格，每行 IP / 端口 / 位置 / 运营商 / 时间
    """
    ignore = False

    urls = [BASE_URL.format(page=page) for page in range(1, MAX_PAGE + 1)]

    def parse(self, html):
        """
        parse html file to get proxies
        """
        doc = pq(html)
        for tr in doc('table.layui-table tbody tr').items():
            tds = tr.find('td')
            host = tds.eq(0).text()
            port = tds.eq(1).text()
            proxy = normalize_proxy(host, port)
            if proxy:
                yield Proxy(host=proxy[0], port=proxy[1])


if __name__ == '__main__':
    crawler = Ip89WebCrawler()
    for proxy in crawler.crawl():
        print(proxy)
