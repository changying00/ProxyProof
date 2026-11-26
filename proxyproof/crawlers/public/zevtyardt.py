from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/zevtyardt/proxy-list/main/{protocol}.txt'


class ZevtyardtCrawler(TextListCrawler):
    """
    zevtyardt/proxy-list crawler, https://github.com/zevtyardt/proxy-list
    """
    urls = [
        BASE_URL.format(protocol='http'),
        BASE_URL.format(protocol='https'),
    ]
    max_proxies = 3000


if __name__ == '__main__':
    crawler = ZevtyardtCrawler()
    for proxy in crawler.crawl():
        print(proxy)
