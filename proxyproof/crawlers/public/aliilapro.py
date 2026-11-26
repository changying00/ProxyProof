from proxyproof.crawlers.base_list import TextListCrawler


BASE_URL = 'https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/{protocol}.txt'


class ALIILAPROCrawler(TextListCrawler):
    """
    ALIILAPRO/Proxy crawler, https://github.com/ALIILAPRO/Proxy
    """
    urls = [
        BASE_URL.format(protocol='http'),
        BASE_URL.format(protocol='https'),
    ]


if __name__ == '__main__':
    crawler = ALIILAPROCrawler()
    for proxy in crawler.crawl():
        print(proxy)
