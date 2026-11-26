from proxyproof.crawlers.base_list import TextListCrawler


# v2 的 displayproxies 接口一次性返回全部可用代理，纯文本 ip:port
BASE_URL = ('https://api.proxyscrape.com/v2/?request=displayproxies'
            '&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all')


class ProxyScrapeCrawler(TextListCrawler):
    """
    proxyscrape crawler, https://proxyscrape.com/
    官方 API，纯文本返回，无需 token
    """
    urls = [BASE_URL]


if __name__ == '__main__':
    crawler = ProxyScrapeCrawler()
    for proxy in crawler.crawl():
        print(proxy)
