from proxyproof.crawlers.base_list import TextListCrawler


BASE_URL = 'https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/{protocol}.txt'


class VakhovCrawler(TextListCrawler):
    """
    vakhov/fresh-proxy-list crawler, https://github.com/vakhov/fresh-proxy-list
    """
    urls = [
        BASE_URL.format(protocol='http'),
        BASE_URL.format(protocol='https'),
    ]


if __name__ == '__main__':
    crawler = VakhovCrawler()
    for proxy in crawler.crawl():
        print(proxy)
