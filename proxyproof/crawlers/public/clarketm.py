from proxyproof.crawlers.base_list import TextListCrawler


BASE_URL = 'https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt'


class ClarketmCrawler(TextListCrawler):
    """
    clarketm/proxy-list crawler, https://github.com/clarketm/proxy-list
    """
    urls = [BASE_URL]


if __name__ == '__main__':
    crawler = ClarketmCrawler()
    for proxy in crawler.crawl():
        print(proxy)
