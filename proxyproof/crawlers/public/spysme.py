from proxyproof.crawlers.base_list import TextListCrawler

BASE_URL = 'https://spys.me/{protocol}.txt'


class SpysMeCrawler(TextListCrawler):
    """
    spys.me crawler, https://spys.me/proxy.txt
    每行格式 `1.2.3.4:8080 US-H-S -`，解析器只取 ip:port
    """
    urls = [
        BASE_URL.format(protocol='proxy'),
        BASE_URL.format(protocol='https'),
    ]


if __name__ == '__main__':
    crawler = SpysMeCrawler()
    for proxy in crawler.crawl():
        print(proxy)
