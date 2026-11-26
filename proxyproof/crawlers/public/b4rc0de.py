from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/{protocol}.txt'


class B4RC0DECrawler(TextListCrawler):
    """
    B4RC0DE-TM/proxy-list crawler, https://github.com/B4RC0DE-TM/proxy-list
    """
    urls = [
        BASE_URL.format(protocol='HTTP'),
        BASE_URL.format(protocol='HTTPS'),
    ]


if __name__ == '__main__':
    crawler = B4RC0DECrawler()
    for proxy in crawler.crawl():
        print(proxy)
