from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/{protocol}.txt'


class RdavydovCrawler(TextListCrawler):
    """
    rdavydov/proxy-list crawler, https://github.com/rdavydov/proxy-list
    """
    urls = [
        BASE_URL.format(protocol='http'),
        BASE_URL.format(protocol='https'),
    ]


if __name__ == '__main__':
    crawler = RdavydovCrawler()
    for proxy in crawler.crawl():
        print(proxy)
