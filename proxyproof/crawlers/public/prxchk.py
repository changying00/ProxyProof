from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/prxchk/proxy-list/main/{protocol}.txt'


class PrxchkCrawler(TextListCrawler):
    """
    prxchk/proxy-list crawler, https://github.com/prxchk/proxy-list
    列表小但存活率较高
    """
    urls = [
        BASE_URL.format(protocol='http'),
        BASE_URL.format(protocol='https'),
    ]


if __name__ == '__main__':
    crawler = PrxchkCrawler()
    for proxy in crawler.crawl():
        print(proxy)
