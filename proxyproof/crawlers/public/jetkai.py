from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-{protocol}.txt'


class JetkaiCrawler(TextListCrawler):
    """
    jetkai/proxy-list crawler, https://github.com/jetkai/proxy-list
    """
    urls = [
        BASE_URL.format(protocol='http'),
        BASE_URL.format(protocol='https'),
    ]


if __name__ == '__main__':
    crawler = JetkaiCrawler()
    for proxy in crawler.crawl():
        print(proxy)
