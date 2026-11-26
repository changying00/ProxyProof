from proxyproof.crawlers.base_list import TextListCrawler


BASE_URL = 'https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/{protocol}.txt'


class Proxy4ParsingCrawler(TextListCrawler):
    """
    proxy4parsing/proxy-list crawler, https://github.com/proxy4parsing/proxy-list
    """
    urls = [
        BASE_URL.format(protocol='http'),
        BASE_URL.format(protocol='https'),
    ]


if __name__ == '__main__':
    crawler = Proxy4ParsingCrawler()
    for proxy in crawler.crawl():
        print(proxy)
