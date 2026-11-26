from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/{protocol}.txt'


class ShiftyTRCrawler(TextListCrawler):
    """
    ShiftyTR/Proxy-List crawler, https://github.com/ShiftyTR/Proxy-List
    """
    urls = [
        BASE_URL.format(protocol='http'),
        BASE_URL.format(protocol='https'),
    ]


if __name__ == '__main__':
    crawler = ShiftyTRCrawler()
    for proxy in crawler.crawl():
        print(proxy)
