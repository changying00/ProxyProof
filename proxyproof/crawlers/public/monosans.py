from proxyproof.crawlers.base_list import TextListCrawler


BASE_URL = 'https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/{protocol}.txt'


class MonosansCrawler(TextListCrawler):
    """
    monosans/proxy-list crawler, https://github.com/monosans/proxy-list
    每 10 分钟刷新一次，HTTP/HTTPS 分文件
    """
    urls = [
        BASE_URL.format(protocol='http'),
        BASE_URL.format(protocol='https'),
    ]


if __name__ == '__main__':
    crawler = MonosansCrawler()
    for proxy in crawler.crawl():
        print(proxy)
